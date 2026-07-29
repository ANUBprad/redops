"""EventPublishingObserver — publishes domain events via EventPublisher.

Translates execution lifecycle hooks into domain events that can
be consumed by external systems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.domain.events.evaluation_events import (
    ItemCompleted,
    ItemFailed,
)
from app.evaluation.execution.contracts.observer import ExecutionObserver
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import EventPublisher
    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.results.results import (
        ExecutionResult,
        StageResult,
        StepResult,
    )


class EventPublishingObserver(ExecutionObserver):
    """Publishes domain events through the EventPublisher contract.

    Each lifecycle hook creates the appropriate domain event and
    publishes it asynchronously. Events are fire-and-forget.
    """

    def __init__(self, event_publisher: EventPublisher) -> None:
        """Initialize with an event publisher."""
        self._event_publisher = event_publisher
        self._run_id: UUIDv7 | None = None

    def set_run_id(self, run_id: UUIDv7) -> None:
        """Set the run ID for subsequent events."""
        self._run_id = run_id

    async def on_execution_started(self, context: PipelineContext) -> None:
        """Execution started is emitted by the domain entity — skip duplicate."""
        self._run_id = context.run_id

    async def on_stage_started(self, stage_name: str, total_steps: int) -> None:
        """Stage start events are informational — no domain event."""

    async def on_stage_completed(self, result: StageResult) -> None:
        """Stage completion events are informational."""

    async def on_step_completed(self, result: StepResult) -> None:
        """Publish item completed or failed event based on outcome."""
        if self._run_id is None:
            return

        item_index = result.metadata.get("item_index", "0")
        event: ItemCompleted | ItemFailed
        if result.is_success:
            event = ItemCompleted(
                run_id=self._run_id,
                item_id=result.step_id,
                item_index=int(item_index),
            )
        else:
            event = ItemFailed(
                run_id=self._run_id,
                item_id=result.step_id,
                item_index=int(item_index),
                error_message=result.error or "Unknown error",
            )
        await self._event_publisher.publish(event)

    async def on_execution_finished(self, result: ExecutionResult) -> None:
        """Execution completion is handled by the orchestrator."""

    async def on_execution_failed(self, result: ExecutionResult) -> None:
        """Execution failure is handled by the orchestrator."""
