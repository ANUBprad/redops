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
        ExecuteItemInput,
        ExecuteItemResult,
        FailRunInput,
        ProgressInput,
        RunIdInput,
        StartRunInput,
        cancel_run_activity,
        complete_run_activity,
        execute_item_activity,
        fail_run_activity,
        queue_run_activity,
        start_run_activity,
        update_progress_activity,
    )


@dataclass(frozen=True, slots=True)
class EvaluationRunWorkflowInput:
    """Input for the evaluation run workflow.

    Attributes:
        run_id: The evaluation run identifier.
        total_items: Number of items to execute.
        provider_name: Provider identifier.
        model_id: Model identifier.
        metric_names: Metrics to evaluate for each item.
        dataset_items: Real item payloads (prompt/reference/context).
        prompt_template: Optional template with ``{variable}`` placeholders.
        system_prompt: Optional system prompt for provider calls.

    """

    run_id: str
    total_items: int = 0
    provider_name: str = ""
    model_id: str = ""
    metric_names: tuple[str, ...] = ()
    dataset_items: tuple[dict[str, str], ...] = ()
    prompt_template: str | None = None
    system_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationRunWorkflowResult:
    """Result of the evaluation run workflow."""

    run_id: str
    status: str
    items_completed: int = 0
    items_total: int = 0
    items_failed: int = 0
    total_cost_usd: float = 0.0
    total_tokens_input: int = 0
    total_tokens_output: int = 0


@workflow.defn
class EvaluationRunWorkflow:
    """Workflow that orchestrates an evaluation run's lifecycle.

    Handles queuing, starting, item execution, progress tracking,
    and completion of an evaluation run. Supports cancellation via signal.
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
        """Execute the evaluation run workflow."""
        activity_start_to_close = timedelta(seconds=30)
        activity_schedule_to_close = timedelta(minutes=5)

        await workflow.execute_activity(
            queue_run_activity,
            RunIdInput(run_id=input.run_id),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        await workflow.execute_activity(
            start_run_activity,
            StartRunInput(run_id=input.run_id, total_items=input.total_items),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        items_completed = 0
        items_failed = 0
        total_cost_usd = 0.0
        total_tokens_input = 0
        total_tokens_output = 0

        for item_index in range(input.total_items):
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
                    items_failed=items_failed,
                    total_cost_usd=total_cost_usd,
                    total_tokens_input=total_tokens_input,
                    total_tokens_output=total_tokens_output,
                )

            try:
                item_data = (
                    input.dataset_items[item_index] if item_index < len(input.dataset_items) else {}
                )
                item_result: ExecuteItemResult = await workflow.execute_activity(
                    execute_item_activity,
                    ExecuteItemInput(
                        run_id=input.run_id,
                        item_index=item_index,
                        provider_name=input.provider_name,
                        model_id=input.model_id,
                        metric_names=input.metric_names,
                        prompt=item_data.get("prompt", ""),
                        reference=item_data.get("reference", ""),
                        context=item_data.get("context", ""),
                        item_id=item_data.get("item_id", ""),
                        prompt_template=input.prompt_template,
                        system_prompt=input.system_prompt,
                    ),
                    start_to_close_timeout=timedelta(seconds=120),
                    schedule_to_close_timeout=timedelta(minutes=5),
                )

                items_completed += 1
                total_cost_usd += item_result.cost_usd
                total_tokens_input += item_result.tokens_input
                total_tokens_output += item_result.tokens_output

                if item_result.failed:
                    items_failed += 1

                await workflow.execute_activity(
                    update_progress_activity,
                    ProgressInput(
                        run_id=input.run_id,
                        items_completed=items_completed,
                        items_failed=items_failed,
                        token_input=total_tokens_input,
                        token_output=total_tokens_output,
                        cost_usd=total_cost_usd,
                        latency_ms=item_result.latency_ms,
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
                        token_input=total_tokens_input,
                        token_output=total_tokens_output,
                        cost_usd=total_cost_usd,
                    ),
                    start_to_close_timeout=activity_start_to_close,
                    schedule_to_close_timeout=activity_schedule_to_close,
                )

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
                items_failed=items_failed,
                total_cost_usd=total_cost_usd,
                total_tokens_input=total_tokens_input,
                total_tokens_output=total_tokens_output,
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
            items_failed=items_failed,
            total_cost_usd=total_cost_usd,
            total_tokens_input=total_tokens_input,
            total_tokens_output=total_tokens_output,
        )
