"""Tests for EvaluationRun Sprint 1.2 enhancements."""

from __future__ import annotations

import pytest

from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import (
    EvaluationType,
    RunStatus,
)
from app.evaluation.domain.events.evaluation_events import (
    EvaluationCancelled,
    EvaluationCompleted,
    EvaluationFailed,
    EvaluationQueued,
)
from app.evaluation.domain.state_machine.run_state_machine import InvalidTransitionError
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
)


def _make_config() -> EvaluationConfiguration:
    """Create a standard test configuration."""
    return EvaluationConfiguration(
        name="Test Eval",
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(
            provider_name="openai",
            model_id="gpt-4",
        ),
        metrics=("accuracy",),
    )


def _make_run(**kwargs: object) -> EvaluationRun:
    """Create a minimal EvaluationRun for testing."""
    return EvaluationRun(
        evaluation_name="Test Eval",
        config=_make_config(),
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        **kwargs,
    )


class TestEvaluationRunNewFields:
    """Tests for Sprint 1.2 field additions."""

    def test_evaluation_id_default_none(self) -> None:
        """evaluation_id defaults to None."""
        run = _make_run()
        assert run.evaluation_id is None

    def test_evaluation_id_set(self) -> None:
        """evaluation_id can be set via constructor."""
        run = _make_run(evaluation_id="eval-123")
        assert run.evaluation_id == "eval-123"

    def test_workflow_id_default_none(self) -> None:
        """workflow_id defaults to None."""
        run = _make_run()
        assert run.workflow_id is None

    def test_workflow_id_set(self) -> None:
        """workflow_id can be set via constructor."""
        run = _make_run(workflow_id="wf-456")
        assert run.workflow_id == "wf-456"

    def test_cancelled_at_default_none(self) -> None:
        """cancelled_at defaults to None."""
        run = _make_run()
        assert run.cancelled_at is None

    def test_token_counts_default_zero(self) -> None:
        """Token counts default to zero."""
        run = _make_run()
        assert run.token_input == 0
        assert run.token_output == 0

    def test_cost_default_zero(self) -> None:
        """Cost defaults to zero."""
        run = _make_run()
        assert run.cost == 0.0

    def test_average_latency_default_zero(self) -> None:
        """Average latency defaults to zero."""
        run = _make_run()
        assert run.average_latency_ms == 0


class TestEvaluationRunProgress:
    """Tests for progress tracking methods."""

    def test_progress_empty(self) -> None:
        """Progress is 0 when no items."""
        run = _make_run()
        assert run.progress == 0.0

    def test_progress_partial(self) -> None:
        """Progress reflects partial completion."""
        run = _make_run()
        run.items_total = 10
        run.items_completed = 3
        assert run.progress == 30.0

    def test_progress_complete(self) -> None:
        """Progress is 100 when all items done."""
        run = _make_run()
        run.items_total = 10
        run.items_completed = 10
        assert run.progress == 100.0

    def test_total_tokens(self) -> None:
        """total_tokens returns sum of input and output."""
        run = _make_run()
        run.token_input = 100
        run.token_output = 50
        assert run.total_tokens == 150

    def test_record_token_usage(self) -> None:
        """record_token_usage accumulates tokens."""
        run = _make_run()
        run.record_token_usage(100, 50)
        run.record_token_usage(200, 30)
        assert run.token_input == 300
        assert run.token_output == 80

    def test_record_cost(self) -> None:
        """record_cost accumulates cost."""
        run = _make_run()
        run.record_cost(0.05)
        run.record_cost(0.03)
        assert abs(run.cost - 0.08) < 1e-10

    def test_record_latency_first_item(self) -> None:
        """record_latency sets latency for first item."""
        run = _make_run()
        run.record_latency(100)
        assert run.average_latency_ms == 100

    def test_record_latency_running_average(self) -> None:
        """record_latency computes running average."""
        run = _make_run()
        run.items_completed = 2
        run.average_latency_ms = 100
        run.record_latency(200)
        # average = (100 * 2 + 200) // 3 = 400 // 3 = 133
        assert run.average_latency_ms == 133


class TestEvaluationRunCancelTimestamp:
    """Tests for cancelled_at timestamp."""

    def test_cancel_sets_cancelled_at(self) -> None:
        """Cancel sets the cancelled_at timestamp."""
        run = _make_run()
        run.queue()
        run.cancel(force=True)
        assert run.cancelled_at is not None

    def test_force_cancel_sets_completed_at(self) -> None:
        """Force cancel also sets completed_at."""
        run = _make_run()
        run.queue()
        run.cancel(force=True)
        assert run.completed_at is not None


class TestEvaluationRunIllegalTransitions:
    """Tests for lifecycle invariant enforcement."""

    def test_cannot_start_twice(self) -> None:
        """Cannot start an already running evaluation."""
        run = _make_run()
        run.queue()
        run.start(total_items=5)
        with pytest.raises(InvalidTransitionError):
            run.start(total_items=5)

    def test_cannot_complete_before_running(self) -> None:
        """Cannot complete a run that hasn't started."""
        run = _make_run()
        run.queue()
        with pytest.raises(InvalidTransitionError):
            run.complete()

    def test_cannot_fail_after_completed(self) -> None:
        """Cannot fail a completed run."""
        run = _make_run()
        run.queue()
        run.start(total_items=1)
        run.record_item_success()
        run.complete()
        with pytest.raises(InvalidTransitionError):
            run.fail(error_code="TEST", error_message="test")

    def test_cannot_cancel_completed(self) -> None:
        """Cannot cancel a completed run."""
        run = _make_run()
        run.queue()
        run.start(total_items=1)
        run.record_item_success()
        run.complete()
        with pytest.raises(InvalidTransitionError):
            run.cancel()

    def test_complete_requires_all_items(self) -> None:
        """Cannot complete unless all items are done."""
        run = _make_run()
        run.queue()
        run.start(total_items=5)
        with pytest.raises(InvalidTransitionError):
            run.complete()

    def test_complete_after_all_items(self) -> None:
        """Can complete after all items are processed."""
        run = _make_run()
        run.queue()
        run.start(total_items=2)
        run.record_item_success()
        run.record_item_success()
        run.complete()
        assert run.status == RunStatus.COMPLETED


class TestEvaluationRunEvents:
    """Tests for domain events with new fields."""

    def test_queue_event(self) -> None:
        """Queue raises EvaluationQueued event."""
        run = _make_run()
        run.queue()
        events = run.collect_events()
        assert any(isinstance(e, EvaluationQueued) for e in events)

    def test_complete_event(self) -> None:
        """Complete raises EvaluationCompleted event."""
        run = _make_run()
        run.queue()
        run.start(total_items=1)
        run.record_item_success()
        run.collect_events()
        run.complete()
        events = run.collect_events()
        assert any(isinstance(e, EvaluationCompleted) for e in events)

    def test_fail_event(self) -> None:
        """Fail raises EvaluationFailed event."""
        run = _make_run()
        run.queue()
        run.start(total_items=1)
        run.collect_events()
        run.fail(error_code="ERR", error_message="boom")
        events = run.collect_events()
        assert any(isinstance(e, EvaluationFailed) for e in events)

    def test_cancel_event(self) -> None:
        """Cancel raises EvaluationCancelled event."""
        run = _make_run()
        run.queue()
        run.start(total_items=1)
        run.collect_events()
        run.cancel(force=True)
        events = run.collect_events()
        assert any(isinstance(e, EvaluationCancelled) for e in events)
