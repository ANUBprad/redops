"""Temporal workflow for evaluation run execution.

Orchestrates the full lifecycle of an evaluation run:
CREATED → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED.

The workflow calls activities that delegate to existing CQRS
handlers, ensuring no duplicate business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.evaluation.temporal.activities import (
        CancelRunInput,
        ExecuteItemInput,
        ExecuteItemResult,
        FailRunInput,
        FinalizeRunIntegrityInput,
        PersistMetricResultsInput,
        ProgressInput,
        RunIdInput,
        StartRunInput,
        cancel_run_activity,
        complete_run_activity,
        execute_item_activity,
        fail_run_activity,
        finalize_run_integrity_activity,
        persist_metric_results_activity,
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


def _compute_workflow_fingerprint(
    *,
    prompt_template: str,
    system_prompt: str,
    provider: str,
    model: str,
    metrics: tuple[str, ...],
) -> str:
    """Compute a deterministic fingerprint for the evaluation configuration.

    Runs inside the workflow (no I/O). Uses SHA-256 for stability.
    """
    import hashlib
    import json

    components: dict[str, str] = {}
    if prompt_template:
        components["prompt_template"] = hashlib.sha256(
            prompt_template.encode(),
        ).hexdigest()[:32]
    if system_prompt:
        components["system_prompt"] = hashlib.sha256(
            system_prompt.encode(),
        ).hexdigest()[:32]
    components["provider"] = provider
    components["model"] = model
    components["metrics"] = json.dumps(sorted(metrics), sort_keys=True)

    canonical = json.dumps(components, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]


def _build_item_trace(item_result: ExecuteItemResult) -> dict[str, Any]:
    """Build a trace dict for a single item from the activity result."""
    metric_traces = []
    for m in item_result.metrics:
        metric_traces.append(
            {
                "metric_name": m.metric_name,
                "score": m.score,
                "normalized_score": m.normalized_score,
                "confidence": m.confidence,
                "reasoning": m.reasoning,
                "version": m.version,
                "cost_usd": m.cost_usd,
                "execution_time_ms": m.execution_time_ms,
                "error": m.error,
            }
        )

    return {
        "item_index": item_result.item_index,
        "prompt_trace": {"prompt": ""},
        "provider_trace": {
            "response_content": item_result.response,
            "tokens_input": item_result.tokens_input,
            "tokens_output": item_result.tokens_output,
            "cost_usd": item_result.cost_usd,
            "latency_ms": item_result.latency_ms,
            "error": item_result.error,
        },
        "metric_traces": metric_traces,
        "total_latency_ms": item_result.latency_ms,
        "total_cost_usd": item_result.cost_usd,
        "error": item_result.error,
    }


@workflow.defn
class EvaluationRunWorkflow:
    """Workflow that orchestrates an evaluation run's lifecycle.

    Handles queuing, starting, item execution, progress tracking,
    and completion of an evaluation run. Supports cancellation via signal.
    Records execution traces and evaluates thresholds at completion.
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

        # Trace: record run start
        started_at = datetime.now(UTC).isoformat()
        item_traces: list[dict[str, Any]] = []
        total_cost_usd = 0.0
        total_tokens_input = 0
        total_tokens_output = 0
        total_latency_ms = 0

        # Compute fingerprint from configuration (no I/O)
        fingerprint = _compute_workflow_fingerprint(
            prompt_template=input.prompt_template or "",
            system_prompt=input.system_prompt or "",
            provider=input.provider_name,
            model=input.model_id,
            metrics=input.metric_names,
        )

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
                total_latency_ms += item_result.latency_ms

                # Record item trace
                item_traces.append(_build_item_trace(item_result))

                if item_result.failed:
                    items_failed += 1
                elif item_result.metrics:
                    await workflow.execute_activity(
                        persist_metric_results_activity,
                        PersistMetricResultsInput(
                            run_id=input.run_id,
                            item_id=item_result.item_id,
                            results=item_result.metrics,
                        ),
                        start_to_close_timeout=activity_start_to_close,
                        schedule_to_close_timeout=activity_schedule_to_close,
                    )

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

        # Build trace data from accumulated item traces
        completed_at = datetime.now(UTC).isoformat()
        trace_data: dict[str, Any] = {
            "run_id": input.run_id,
            "evaluation_name": "",
            "provider_name": input.provider_name,
            "model_id": input.model_id,
            "started_at": started_at,
            "completed_at": completed_at,
            "status": "completed" if items_failed < input.total_items else "failed",
            "item_traces": item_traces,
            "total_cost_usd": total_cost_usd,
            "total_tokens_input": total_tokens_input,
            "total_tokens_output": total_tokens_output,
            "total_latency_ms": total_latency_ms,
            "configuration": {
                "provider": input.provider_name,
                "model": input.model_id,
                "metrics": list(input.metric_names),
                "prompt_template": input.prompt_template,
                "system_prompt": input.system_prompt,
            },
        }

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

            # Finalize integrity with error verdict
            await workflow.execute_activity(
                finalize_run_integrity_activity,
                FinalizeRunIntegrityInput(
                    run_id=input.run_id,
                    metric_names=input.metric_names,
                    trace_data=trace_data,
                    fingerprint=fingerprint,
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

        # Finalize integrity: evaluate thresholds, capture provenance, persist
        await workflow.execute_activity(
            finalize_run_integrity_activity,
            FinalizeRunIntegrityInput(
                run_id=input.run_id,
                metric_names=input.metric_names,
                trace_data=trace_data,
                fingerprint=fingerprint,
            ),
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
