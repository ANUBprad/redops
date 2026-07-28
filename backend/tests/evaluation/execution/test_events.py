"""Tests for the events module."""

from __future__ import annotations

from app.evaluation.execution.events.events import (
    ExecutionAborted,
    ExecutionFinished,
    ExecutionPaused,
    ExecutionPlanned,
    ExecutionResumed,
    PipelineBuilt,
    StageCompleted,
    StageFailed,
    StageStarted,
)
from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7


class TestExecutionEvents:
    """Tests for all execution events."""

    def test_execution_planned(self) -> None:
        """Verify ExecutionPlanned event."""
        event = ExecutionPlanned(
            run_id=UUIDv7.generate(),
            plan_id=UUIDv7.generate(),
            total_stages=3,
            total_steps=10,
        )
        assert event.event_type == "execution.planned"
        assert event.total_stages == 3
        assert event.total_steps == 10
        assert event.event_id is not None

    def test_pipeline_built(self) -> None:
        """Verify PipelineBuilt event."""
        event = PipelineBuilt(
            run_id=UUIDv7.generate(),
            plan_id=UUIDv7.generate(),
            stage_count=5,
        )
        assert event.event_type == "execution.pipeline.built"
        assert event.stage_count == 5

    def test_stage_started(self) -> None:
        """Verify StageStarted event."""
        event = StageStarted(
            run_id=UUIDv7.generate(),
            stage_type=StageType.PROVIDER_INVOCATION,
            stage_name="Invoke",
            total_steps=20,
        )
        assert event.event_type == "execution.stage.started"
        assert event.stage_type == StageType.PROVIDER_INVOCATION
        assert event.stage_name == "Invoke"
        assert event.total_steps == 20

    def test_stage_completed(self) -> None:
        """Verify StageCompleted event."""
        event = StageCompleted(
            run_id=UUIDv7.generate(),
            stage_type=StageType.AGGREGATION,
            stage_name="Aggregate",
            duration_ms=500,
            steps_succeeded=10,
            steps_failed=0,
        )
        assert event.event_type == "execution.stage.completed"
        assert event.duration_ms == 500
        assert event.steps_succeeded == 10

    def test_stage_failed(self) -> None:
        """Verify StageFailed event."""
        event = StageFailed(
            run_id=UUIDv7.generate(),
            stage_type=StageType.PERSISTENCE,
            stage_name="Persist",
            error_message="Connection lost",
        )
        assert event.event_type == "execution.stage.failed"
        assert event.error_message == "Connection lost"

    def test_execution_paused(self) -> None:
        """Verify ExecutionPaused event."""
        event = ExecutionPaused(
            run_id=UUIDv7.generate(),
            current_stage=StageType.PROVIDER_INVOCATION,
            items_completed=50,
            items_total=100,
        )
        assert event.event_type == "execution.paused"
        assert event.items_completed == 50
        assert event.items_total == 100

    def test_execution_resumed(self) -> None:
        """Verify ExecutionResumed event."""
        event = ExecutionResumed(
            run_id=UUIDv7.generate(),
            current_stage=StageType.PROVIDER_INVOCATION,
            items_completed=50,
            items_total=100,
        )
        assert event.event_type == "execution.resumed"

    def test_execution_finished(self) -> None:
        """Verify ExecutionFinished event."""
        event = ExecutionFinished(
            run_id=UUIDv7.generate(),
            total_duration_ms=5000,
            stages_succeeded=7,
            stages_total=7,
            items_succeeded=90,
            items_failed=10,
            items_total=100,
        )
        assert event.event_type == "execution.finished"
        assert event.items_succeeded == 90
        assert event.items_total == 100

    def test_execution_aborted(self) -> None:
        """Verify ExecutionAborted event."""
        event = ExecutionAborted(
            run_id=UUIDv7.generate(),
            reason="Budget exceeded",
            is_cancellation=True,
            total_duration_ms=3000,
        )
        assert event.event_type == "execution.aborted"
        assert event.reason == "Budget exceeded"
        assert event.is_cancellation

    def test_event_immutability(self) -> None:
        """Verify all events are frozen."""
        event = ExecutionPlanned(run_id=UUIDv7.generate(), plan_id=UUIDv7.generate())
        try:
            event.total_stages = 99  # type: ignore
            assert False, "Should have raised AttributeError"
        except AttributeError:
            pass

    def test_default_event_id(self) -> None:
        """Verify events auto-generate event_id."""
        event = ExecutionFinished(run_id=UUIDv7.generate())
        assert event.event_id is not None
        assert isinstance(event.event_id, UUIDv7)

    def test_occurred_at(self) -> None:
        """Verify events have occurred_at timestamp."""
        event = ExecutionPlanned(run_id=UUIDv7.generate(), plan_id=UUIDv7.generate())
        assert event.occurred_at is not None
