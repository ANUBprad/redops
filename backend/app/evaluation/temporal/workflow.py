"""Temporal workflow for evaluation run execution.

Orchestrates the full lifecycle of an evaluation run:
CREATED → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED.

The workflow calls activities that delegate to existing CQRS
handlers, ensuring no duplicate business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.evaluation.temporal.activities import (
        CancelRunInput,
        FailRunInput,
        ProgressInput,
        RunIdInput,
        StartRunInput,
        cancel_run_activity,
        complete_run_activity,
        fail_run_activity,
        queue_run_activity,
        start_run_activity,
        update_progress_activity,
    )


@dataclass(frozen=True, slots=True)
class EvaluationRunWorkflowInput:
    """Input for the evaluation run workflow."""

    run_id: str
    total_items: int = 0


@dataclass(frozen=True, slots=True)
class EvaluationRunWorkflowResult:
    """Result of the evaluation run workflow."""

    run_id: str
    status: str
    items_completed: int = 0
    items_total: int = 0


@workflow.defn
class EvaluationRunWorkflow:
    """Workflow that orchestrates an evaluation run's lifecycle.

    Handles queuing, starting, progress tracking, and completion
    of an evaluation run. Supports cancellation via signal.
    """

    def __init__(self) -> None:
        """Initialize workflow state."""
        self._cancel_requested: bool = False

    @workflow.signal
    def cancel(self) -> None:
        """Signal to request cancellation of the run."""
        self._cancel_requested = True

    @workflow.run
    async def run(
        self,
        input: EvaluationRunWorkflowInput,
    ) -> EvaluationRunWorkflowResult:
        """Execute the evaluation run workflow.

        Args:
            input: Workflow input containing run_id and total_items.

        Returns:
            Workflow result with final status and counts.

        """
        activity_start_to_close = timedelta(seconds=30)
        activity_schedule_to_close = timedelta(minutes=5)

        # Step 1: Queue the run
        await workflow.execute_activity(
            queue_run_activity,
            RunIdInput(run_id=input.run_id),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        # Step 2: Start the run
        await workflow.execute_activity(
            start_run_activity,
            StartRunInput(run_id=input.run_id, total_items=input.total_items),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        # Step 3: Process items (simulated progress loop)
        items_completed = 0
        items_failed = 0

        for _item_index in range(input.total_items):
            # Check for cancellation
            if self._cancel_requested:
                await workflow.execute_activity(
                    cancel_run_activity,
                    CancelRunInput(
                        run_id=input.run_id,
                        reason="user_cancelled",
                        force=True,
                    ),
                    start_to_close_timeout=activity_start_to_close,
                    schedule_to_close_timeout=activity_schedule_to_close,
                )
                return EvaluationRunWorkflowResult(
                    run_id=input.run_id,
                    status="cancelled",
                    items_completed=items_completed,
                    items_total=input.total_items,
                )

            # Simulate item processing (replace with real execution)
            try:
                items_completed += 1
                await workflow.execute_activity(
                    update_progress_activity,
                    ProgressInput(
                        run_id=input.run_id,
                        items_completed=items_completed,
                        items_failed=items_failed,
                    ),
                    start_to_close_timeout=activity_start_to_close,
                    schedule_to_close_timeout=activity_schedule_to_close,
                )
            except Exception:
                items_failed += 1
                items_completed += 1
                await workflow.execute_activity(
                    update_progress_activity,
                    ProgressInput(
                        run_id=input.run_id,
                        items_completed=items_completed,
                        items_failed=items_failed,
                    ),
                    start_to_close_timeout=activity_start_to_close,
                    schedule_to_close_timeout=activity_schedule_to_close,
                )

        # Step 4: Complete the run
        if items_failed == input.total_items:
            await workflow.execute_activity(
                fail_run_activity,
                FailRunInput(
                    run_id=input.run_id,
                    error_code="ALL_ITEMS_FAILED",
                    error_message="All items failed during execution",
                ),
                start_to_close_timeout=activity_start_to_close,
                schedule_to_close_timeout=activity_schedule_to_close,
            )
            return EvaluationRunWorkflowResult(
                run_id=input.run_id,
                status="failed",
                items_completed=items_completed,
                items_total=input.total_items,
            )

        await workflow.execute_activity(
            complete_run_activity,
            RunIdInput(run_id=input.run_id),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        return EvaluationRunWorkflowResult(
            run_id=input.run_id,
            status="completed",
            items_completed=items_completed,
            items_total=input.total_items,
        )
