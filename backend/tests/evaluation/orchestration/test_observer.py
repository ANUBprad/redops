"""Tests for EventPublishingObserver."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.evaluation.domain.events.evaluation_events import (
    ItemCompleted,
    ItemFailed,
)
from app.evaluation.execution.pipeline.step import StepStatus
from app.evaluation.execution.results.results import ExecutionOutcome, StageResult, StepResult
from app.evaluation.execution.stages.types import StageType
from app.evaluation.orchestration.observer import EventPublishingObserver


class TestEventPublishingObserver:
    """Tests for EventPublishingObserver lifecycle hooks."""

    async def test_on_execution_started_sets_run_id(self, sample_context) -> None:
        """Execution started should set run_id for subsequent events."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)

        await observer.on_execution_started(sample_context)

        assert observer._run_id == sample_context.run_id
        publisher.publish.assert_not_called()

    async def test_on_stage_started_no_publish(self) -> None:
        """Stage started should not publish any event."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)

        await observer.on_stage_started("test_stage", 5)
        publisher.publish.assert_not_called()

    async def test_on_stage_completed_no_publish(self) -> None:
        """Stage completed should not publish any event."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)

        result = StageResult(
            stage_type=StageType.PROVIDER_INVOCATION,
            stage_name="test",
            outcome=ExecutionOutcome.SUCCESS,
        )
        await observer.on_stage_completed(result)
        publisher.publish.assert_not_called()

    async def test_on_step_completed_success_publishes_item_completed(self) -> None:
        """Successful step should publish ItemCompleted event."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)
        observer.set_run_id(MagicMock())

        step_result = StepResult(
            step_id=MagicMock(),
            step_name="step_0",
            stage_type=StageType.PROVIDER_INVOCATION,
            status=StepStatus.COMPLETED,
            outcome=ExecutionOutcome.SUCCESS,
        )
        await observer.on_step_completed(step_result)

        publisher.publish.assert_called_once()
        event = publisher.publish.call_args[0][0]
        assert isinstance(event, ItemCompleted)

    async def test_on_step_completed_failure_publishes_item_failed(self) -> None:
        """Failed step should publish ItemFailed event."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)
        observer.set_run_id(MagicMock())

        step_result = StepResult(
            step_id=MagicMock(),
            step_name="step_0",
            stage_type=StageType.PROVIDER_INVOCATION,
            status=StepStatus.FAILED,
            outcome=ExecutionOutcome.FAILURE,
            error="provider timeout",
        )
        await observer.on_step_completed(step_result)

        publisher.publish.assert_called_once()
        event = publisher.publish.call_args[0][0]
        assert isinstance(event, ItemFailed)
        assert event.error_message == "provider timeout"

    async def test_on_step_completed_failure_with_no_error(self) -> None:
        """Failed step with no error message should use default."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)
        observer.set_run_id(MagicMock())

        step_result = StepResult(
            step_id=MagicMock(),
            step_name="step_0",
            stage_type=StageType.PROVIDER_INVOCATION,
            status=StepStatus.FAILED,
            outcome=ExecutionOutcome.FAILURE,
            error=None,
        )
        await observer.on_step_completed(step_result)

        event = publisher.publish.call_args[0][0]
        assert isinstance(event, ItemFailed)
        assert event.error_message == "Unknown error"

    async def test_on_step_completed_no_run_id_no_publish(self) -> None:
        """Step completed without run_id should not publish."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)

        step_result = StepResult(
            step_id=MagicMock(),
            step_name="step_0",
            stage_type=StageType.PROVIDER_INVOCATION,
            status=StepStatus.COMPLETED,
            outcome=ExecutionOutcome.SUCCESS,
        )
        await observer.on_step_completed(step_result)
        publisher.publish.assert_not_called()

    async def test_on_execution_finished_no_publish(self) -> None:
        """Execution finished should not publish any event."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)

        result = MagicMock()
        await observer.on_execution_finished(result)
        publisher.publish.assert_not_called()

    async def test_on_execution_failed_no_publish(self) -> None:
        """Execution failed should not publish any event."""
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        observer = EventPublishingObserver(publisher)

        result = MagicMock()
        await observer.on_execution_failed(result)
        publisher.publish.assert_not_called()
