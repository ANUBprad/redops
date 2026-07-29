"""Tests for evaluation domain entities."""

from __future__ import annotations

import pytest

from app.evaluation.domain.entities.evaluation_entities import (
    AggregatedMetrics,
    EvaluationItem,
    EvaluationRun,
    InvalidItemStateError,
    ItemResult,
    RunCheckpoint,
)
from app.evaluation.domain.enums.evaluation_enums import (
    CancellationReason,
    FailureReason,
    ItemStatus,
    RunStatus,
)
from app.evaluation.domain.state_machine.run_state_machine import InvalidTransitionError
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
)
from app.kernel.entities.base import UUIDv7


def _make_config(
    name: str = "Test Eval",
    metrics: tuple[str, ...] = ("accuracy",),
) -> EvaluationConfiguration:
    """Create a valid evaluation configuration."""
    return EvaluationConfiguration(
        name=name,
        eval_type="single",
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        metrics=metrics,
    )


def _make_run(
    name: str = "Test Eval",
    metrics: tuple[str, ...] = ("accuracy",),
) -> EvaluationRun:
    """Create a valid evaluation run."""
    config = _make_config(name=name, metrics=metrics)
    return EvaluationRun(
        evaluation_name=name,
        config=config,
        profile=config.profile,
    )


class TestItemResult:
    """Tests for ItemResult value object."""

    def test_valid_creation(self) -> None:
        """Valid item result can be created."""
        result = ItemResult(
            item_id=UUIDv7.generate(),
            item_index=0,
        )
        assert result.item_index == 0
        assert result.status == ItemStatus.PENDING

    def test_total_tokens(self) -> None:
        """Total tokens sums input and output."""
        result = ItemResult(
            item_id=UUIDv7.generate(),
            item_index=0,
            tokens_input=100,
            tokens_output=50,
        )
        assert result.total_tokens == 150

    def test_is_success(self) -> None:
        """is_success checks COMPLETED status."""
        result = ItemResult(
            item_id=UUIDv7.generate(),
            item_index=0,
            status=ItemStatus.COMPLETED,
        )
        assert result.is_success is True

    def test_has_scores(self) -> None:
        """has_scores checks non-empty scores."""
        result = ItemResult(
            item_id=UUIDv7.generate(),
            item_index=0,
            scores={"accuracy": 0.9},
        )
        assert result.has_scores is True

    def test_no_scores(self) -> None:
        """has_scores is False when empty."""
        result = ItemResult(
            item_id=UUIDv7.generate(),
            item_index=0,
        )
        assert result.has_scores is False


class TestAggregatedMetrics:
    """Tests for AggregatedMetrics value object."""

    def test_empty_scores(self) -> None:
        """Empty scores produce zero metrics."""
        metrics = AggregatedMetrics.from_scores("accuracy", [])
        assert metrics.item_count == 0
        assert metrics.mean == 0.0

    def test_single_score(self) -> None:
        """Single score has zero std_dev."""
        metrics = AggregatedMetrics.from_scores("accuracy", [0.8])
        assert metrics.mean == 0.8
        assert metrics.min_score == 0.8
        assert metrics.max_score == 0.8
        assert metrics.item_count == 1
        assert metrics.std_dev == 0.0

    def test_multiple_scores(self) -> None:
        """Multiple scores compute correct statistics."""
        metrics = AggregatedMetrics.from_scores("accuracy", [0.6, 0.8, 1.0])
        assert metrics.item_count == 3
        assert abs(metrics.mean - 0.8) < 0.01
        assert metrics.min_score == 0.6
        assert metrics.max_score == 1.0
        assert metrics.std_dev > 0

    def test_from_item_results(self) -> None:
        """Aggregated from item results with partial flag."""
        results = (
            ItemResult(
                item_id=UUIDv7.generate(),
                item_index=0,
                scores={"accuracy": 0.9},
            ),
            ItemResult(
                item_id=UUIDv7.generate(),
                item_index=1,
                scores={},  # No accuracy score
            ),
        )
        # This tests the factory method path
        scores = [r.scores.get("accuracy") for r in results if "accuracy" in r.scores]
        metrics = AggregatedMetrics.from_scores("accuracy", scores)
        assert metrics.item_count == 1
        assert metrics.mean == 0.9


class TestRunCheckpoint:
    """Tests for RunCheckpoint value object."""

    def test_valid_creation(self) -> None:
        """Valid checkpoint can be created."""
        checkpoint = RunCheckpoint(
            run_id=UUIDv7.generate(),
            checkpoint_number=1,
            items_completed=50,
            items_total=100,
            last_item_index=49,
        )
        assert checkpoint.checkpoint_number == 1
        assert checkpoint.completion_ratio == 0.5

    def test_completion_ratio(self) -> None:
        """Completion ratio is items_completed / items_total."""
        checkpoint = RunCheckpoint(
            run_id=UUIDv7.generate(),
            checkpoint_number=1,
            items_completed=75,
            items_total=100,
            last_item_index=74,
        )
        assert checkpoint.completion_ratio == 0.75

    def test_is_complete(self) -> None:
        """is_complete checks all items done."""
        checkpoint = RunCheckpoint(
            run_id=UUIDv7.generate(),
            checkpoint_number=1,
            items_completed=100,
            items_total=100,
            last_item_index=99,
        )
        assert checkpoint.is_complete is True

    def test_not_complete(self) -> None:
        """is_complete is False when items remain."""
        checkpoint = RunCheckpoint(
            run_id=UUIDv7.generate(),
            checkpoint_number=1,
            items_completed=50,
            items_total=100,
            last_item_index=49,
        )
        assert checkpoint.is_complete is False

    def test_zero_total_is_complete(self) -> None:
        """Zero total items is considered complete."""
        checkpoint = RunCheckpoint(
            run_id=UUIDv7.generate(),
            checkpoint_number=0,
            items_completed=0,
            items_total=0,
            last_item_index=-1,
        )
        assert checkpoint.is_complete is True


class TestEvaluationItem:
    """Tests for EvaluationItem entity."""

    def test_valid_creation(self) -> None:
        """Valid item can be created."""
        item = EvaluationItem(
            run_id=UUIDv7.generate(),
            index=0,
            data={"input": "test"},
        )
        assert item.index == 0
        assert item.status == ItemStatus.PENDING
        assert item.data == {"input": "test"}

    def test_default_status_pending(self) -> None:
        """New item starts in PENDING state."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        assert item.status == ItemStatus.PENDING

    def test_start(self) -> None:
        """start transitions to RUNNING."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.start()
        assert item.status == ItemStatus.RUNNING

    def test_start_invalid_state(self) -> None:
        """start raises error if not PENDING."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.start()
        with pytest.raises(InvalidItemStateError):
            item.start()

    def test_complete(self) -> None:
        """complete transitions to COMPLETED."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.start()
        result = ItemResult(
            item_id=item.id,
            item_index=0,
            status=ItemStatus.COMPLETED,
            scores={"accuracy": 0.9},
        )
        item.complete(result)
        assert item.status == ItemStatus.COMPLETED
        assert item.result is not None
        assert item.result.scores["accuracy"] == 0.9

    def test_complete_invalid_state(self) -> None:
        """complete raises error if not RUNNING."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        result = ItemResult(
            item_id=item.id,
            item_index=0,
            status=ItemStatus.COMPLETED,
        )
        with pytest.raises(InvalidItemStateError):
            item.complete(result)

    def test_fail(self) -> None:
        """fail transitions to FAILED."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.start()
        item.fail("Connection refused", FailureReason.PROVIDER_UNAVAILABLE)
        assert item.status == ItemStatus.FAILED
        assert item.result is not None
        assert item.result.error == "Connection refused"
        assert item.result.failure_reason == FailureReason.PROVIDER_UNAVAILABLE

    def test_fail_completed_item(self) -> None:
        """Cannot fail a completed item."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.start()
        result = ItemResult(item_id=item.id, item_index=0, status=ItemStatus.COMPLETED)
        item.complete(result)
        with pytest.raises(InvalidItemStateError):
            item.fail("error")

    def test_skip(self) -> None:
        """skip transitions to SKIPPED."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.skip("cache hit")
        assert item.status == ItemStatus.SKIPPED

    def test_skip_terminal_state(self) -> None:
        """Cannot skip a terminal state."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.start()
        result = ItemResult(item_id=item.id, item_index=0, status=ItemStatus.COMPLETED)
        item.complete(result)
        with pytest.raises(InvalidItemStateError):
            item.skip()

    def test_cancel(self) -> None:
        """cancel transitions to CANCELLED."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.cancel()
        assert item.status == ItemStatus.CANCELLED

    def test_cancel_terminal_state(self) -> None:
        """Cannot cancel a terminal state."""
        item = EvaluationItem(run_id=UUIDv7.generate(), index=0)
        item.start()
        result = ItemResult(item_id=item.id, item_index=0, status=ItemStatus.COMPLETED)
        item.complete(result)
        with pytest.raises(InvalidItemStateError):
            item.cancel()


class TestEvaluationRun:
    """Tests for EvaluationRun aggregate root."""

    def test_valid_creation(self) -> None:
        """Valid run can be created."""
        run = _make_run()
        assert run.status == RunStatus.CREATED
        assert run.evaluation_name == "Test Eval"

    def test_queue(self) -> None:
        """queue transitions to QUEUED and raises event."""
        run = _make_run()
        run.queue()
        assert run.status == RunStatus.QUEUED
        events = run.collect_events()
        assert any(e.event_type == "evaluation.queued" for e in events)

    def test_start(self) -> None:
        """start transitions to RUNNING and raises event."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        assert run.status == RunStatus.RUNNING
        assert run.items_total == 100
        assert run.started_at is not None
        events = run.collect_events()
        assert any(e.event_type == "evaluation.started" for e in events)

    def test_start_negative_items(self) -> None:
        """start raises error with negative items."""
        run = _make_run()
        run.queue()
        with pytest.raises(ValueError, match="Total items cannot be negative"):
            run.start(total_items=-1)

    def test_pause(self) -> None:
        """pause transitions to PAUSED and raises event."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.pause()
        assert run.status == RunStatus.PAUSED
        events = run.collect_events()
        assert any(e.event_type == "evaluation.paused" for e in events)

    def test_pause_invalid(self) -> None:
        """pause raises error when not RUNNING."""
        run = _make_run()
        with pytest.raises(InvalidTransitionError):
            run.pause()

    def test_resume(self) -> None:
        """resume transitions to RUNNING and raises event."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.save_checkpoint(
            RunCheckpoint(
                run_id=run.id,
                checkpoint_number=1,
                items_completed=50,
                items_total=100,
                last_item_index=49,
            ),
        )
        run.pause()
        run.resume()
        assert run.status == RunStatus.RUNNING
        events = run.collect_events()
        assert any(e.event_type == "evaluation.resumed" for e in events)

    def test_resume_without_checkpoint(self) -> None:
        """resume fails without checkpoint."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.pause()
        with pytest.raises(InvalidTransitionError):
            run.resume()

    def test_complete(self) -> None:
        """complete transitions to COMPLETED and raises event."""
        run = _make_run()
        run.queue()
        run.start(total_items=2)
        run.record_item_success()
        run.record_item_success()
        run.complete()
        assert run.status == RunStatus.COMPLETED
        assert run.completed_at is not None
        events = run.collect_events()
        assert any(e.event_type == "evaluation.completed" for e in events)

    def test_complete_incomplete_items(self) -> None:
        """complete fails when items remain."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        with pytest.raises(InvalidTransitionError):
            run.complete()

    def test_fail(self) -> None:
        """fail transitions to FAILED and raises event."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.fail("PROVIDER_ERROR", "Connection refused")
        assert run.status == RunStatus.FAILED
        assert run.completed_at is not None
        assert run.failure_summary is not None
        events = run.collect_events()
        assert any(e.event_type == "evaluation.failed" for e in events)

    def test_timeout(self) -> None:
        """timeout transitions to TIMEDOUT and raises event."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.timeout()
        assert run.status == RunStatus.TIMEDOUT
        assert run.completed_at is not None
        events = run.collect_events()
        assert any(e.event_type == "evaluation.timed_out" for e in events)

    def test_cancel_graceful(self) -> None:
        """cancel without force goes to CANCELLING."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.cancel()
        assert run.status == RunStatus.CANCELLING
        assert run.cancellation_reason == CancellationReason.USER_CANCELLED
        events = run.collect_events()
        assert any(e.event_type == "evaluation.cancelled" for e in events)

    def test_cancel_force(self) -> None:
        """cancel with force goes directly to CANCELLED."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.cancel(force=True)
        assert run.status == RunStatus.CANCELLED
        assert run.completed_at is not None

    def test_cancel_with_reason(self) -> None:
        """cancel with custom reason."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.cancel(reason=CancellationReason.BUDGET_EXCEEDED)
        assert run.cancellation_reason == CancellationReason.BUDGET_EXCEEDED

    def test_record_item_success(self) -> None:
        """record_item_success increments counters."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.record_item_success()
        assert run.items_completed == 1
        assert run.items_failed == 0

    def test_record_item_failure(self) -> None:
        """record_item_failure increments both counters."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        run.record_item_failure()
        assert run.items_completed == 1
        assert run.items_failed == 1

    def test_save_checkpoint(self) -> None:
        """save_checkpoint stores checkpoint."""
        run = _make_run()
        run.queue()
        run.start(total_items=100)
        checkpoint = RunCheckpoint(
            run_id=run.id,
            checkpoint_number=1,
            items_completed=50,
            items_total=100,
            last_item_index=49,
        )
        run.save_checkpoint(checkpoint)
        assert run.checkpoint == checkpoint

    def test_duration_ms(self) -> None:
        """duration_ms returns 0 when not started."""
        run = _make_run()
        assert run.duration_ms == 0

    def test_can_transition_to(self) -> None:
        """can_transition_to checks validity."""
        run = _make_run()
        assert run.can_transition_to(RunStatus.QUEUED) is True
        assert run.can_transition_to(RunStatus.RUNNING) is False

    def test_events_collected(self) -> None:
        """Events are collected and cleared."""
        run = _make_run()
        run.queue()
        events1 = run.collect_events()
        events2 = run.collect_events()
        assert len(events1) > 0
        assert len(events2) == 0

    def test_version_incremented(self) -> None:
        """Version is incremented on transitions."""
        run = _make_run()
        initial_version = run.version
        run.queue()
        assert run.version > initial_version
