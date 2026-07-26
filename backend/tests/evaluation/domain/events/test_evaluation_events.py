"""Tests for evaluation domain events."""

from __future__ import annotations

import pytest

from app.evaluation.domain.enums.evaluation_enums import (
    CancellationReason,
    FailureReason,
)
from app.evaluation.domain.events.evaluation_events import (
    CheckpointCreated,
    CheckpointLoaded,
    EvaluationCancelled,
    EvaluationCompleted,
    EvaluationCreated,
    EvaluationFailed,
    EvaluationPaused,
    EvaluationQueued,
    EvaluationResumed,
    EvaluationStarted,
    EvaluationTimedOut,
    ItemCancelled,
    ItemCompleted,
    ItemFailed,
    ItemRetried,
    ItemSkipped,
    ItemStarted,
    MetricAggregated,
    MetricComputed,
    MetricFailed,
)
from app.kernel.entities.base import UUIDv7


class TestEvaluationCreated:
    """Tests for EvaluationCreated event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.created."""
        event = EvaluationCreated()
        assert event.event_type == "evaluation.created"

    def test_has_event_id(self) -> None:
        """Event has an auto-generated event_id."""
        event = EvaluationCreated()
        assert isinstance(event.event_id, UUIDv7)

    def test_has_timestamp(self) -> None:
        """Event has an occurred_at timestamp."""
        event = EvaluationCreated()
        assert event.occurred_at is not None

    def test_correlation_id(self) -> None:
        """Event can have a correlation_id."""
        event = EvaluationCreated(correlation_id="corr-001")
        assert event.correlation_id == "corr-001"

    def test_payload_fields(self) -> None:
        """Event carries payload fields."""
        run_id = UUIDv7.generate()
        event = EvaluationCreated(
            run_id=run_id,
            evaluation_name="Test",
            eval_type="dataset",
            provider_name="openai",
            model_id="gpt-4",
        )
        assert event.run_id == run_id
        assert event.evaluation_name == "Test"


class TestEvaluationQueued:
    """Tests for EvaluationQueued event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.queued."""
        event = EvaluationQueued()
        assert event.event_type == "evaluation.queued"


class TestEvaluationStarted:
    """Tests for EvaluationStarted event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.started."""
        event = EvaluationStarted()
        assert event.event_type == "evaluation.started"

    def test_total_items(self) -> None:
        """Event carries total_items."""
        event = EvaluationStarted(total_items=100)
        assert event.total_items == 100


class TestEvaluationPaused:
    """Tests for EvaluationPaused event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.paused."""
        event = EvaluationPaused()
        assert event.event_type == "evaluation.paused"


class TestEvaluationResumed:
    """Tests for EvaluationResumed event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.resumed."""
        event = EvaluationResumed()
        assert event.event_type == "evaluation.resumed"


class TestEvaluationCompleted:
    """Tests for EvaluationCompleted event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.completed."""
        event = EvaluationCompleted()
        assert event.event_type == "evaluation.completed"

    def test_duration(self) -> None:
        """Event carries duration_ms."""
        event = EvaluationCompleted(duration_ms=5000)
        assert event.duration_ms == 5000


class TestEvaluationCancelled:
    """Tests for EvaluationCancelled event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.cancelled."""
        event = EvaluationCancelled()
        assert event.event_type == "evaluation.cancelled"

    def test_default_reason(self) -> None:
        """Default reason is USER_CANCELLED."""
        event = EvaluationCancelled()
        assert event.reason == CancellationReason.USER_CANCELLED

    def test_force_flag(self) -> None:
        """Force flag is carried."""
        event = EvaluationCancelled(force=True)
        assert event.force is True


class TestEvaluationFailed:
    """Tests for EvaluationFailed event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.failed."""
        event = EvaluationFailed()
        assert event.event_type == "evaluation.failed"

    def test_error_details(self) -> None:
        """Event carries error details."""
        event = EvaluationFailed(
            error_code="PROVIDER_ERROR",
            error_message="Connection refused",
        )
        assert event.error_code == "PROVIDER_ERROR"
        assert event.error_message == "Connection refused"


class TestEvaluationTimedOut:
    """Tests for EvaluationTimedOut event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.timed_out."""
        event = EvaluationTimedOut()
        assert event.event_type == "evaluation.timed_out"


class TestItemStarted:
    """Tests for ItemStarted event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.item.started."""
        event = ItemStarted()
        assert event.event_type == "evaluation.item.started"


class TestItemCompleted:
    """Tests for ItemCompleted event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.item.completed."""
        event = ItemCompleted()
        assert event.event_type == "evaluation.item.completed"

    def test_cost(self) -> None:
        """Event carries cost_usd."""
        event = ItemCompleted(cost_usd=0.05)
        assert event.cost_usd == 0.05


class TestItemFailed:
    """Tests for ItemFailed event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.item.failed."""
        event = ItemFailed()
        assert event.event_type == "evaluation.item.failed"

    def test_failure_reason(self) -> None:
        """Event carries failure_reason."""
        event = ItemFailed(failure_reason=FailureReason.PROVIDER_TIMEOUT)
        assert event.failure_reason == FailureReason.PROVIDER_TIMEOUT


class TestItemRetried:
    """Tests for ItemRetried event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.item.retried."""
        event = ItemRetried()
        assert event.event_type == "evaluation.item.retried"


class TestItemCancelled:
    """Tests for ItemCancelled event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.item.cancelled."""
        event = ItemCancelled()
        assert event.event_type == "evaluation.item.cancelled"


class TestItemSkipped:
    """Tests for ItemSkipped event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.item.skipped."""
        event = ItemSkipped()
        assert event.event_type == "evaluation.item.skipped"


class TestMetricComputed:
    """Tests for MetricComputed event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.metric.computed."""
        event = MetricComputed()
        assert event.event_type == "evaluation.metric.computed"


class TestMetricFailed:
    """Tests for MetricFailed event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.metric.failed."""
        event = MetricFailed()
        assert event.event_type == "evaluation.metric.failed"


class TestMetricAggregated:
    """Tests for MetricAggregated event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.metric.aggregated."""
        event = MetricAggregated()
        assert event.event_type == "evaluation.metric.aggregated"


class TestCheckpointCreated:
    """Tests for CheckpointCreated event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.checkpoint.created."""
        event = CheckpointCreated()
        assert event.event_type == "evaluation.checkpoint.created"


class TestCheckpointLoaded:
    """Tests for CheckpointLoaded event."""

    def test_event_type(self) -> None:
        """Event type is evaluation.checkpoint.loaded."""
        event = CheckpointLoaded()
        assert event.event_type == "evaluation.checkpoint.loaded"
