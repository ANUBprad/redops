"""EvaluationPipelineExecutor and stage executors.

Concrete implementations of the PipelineExecutor and ExecutionStage
contracts for evaluation execution.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.evaluation.execution.contracts.executor import PipelineExecutor
from app.evaluation.execution.pipeline.step import ExecutionStep, StepStatus
from app.evaluation.execution.results.results import (
    ExecutionOutcome,
    ExecutionResult,
    StageResult,
    StepResult,
)
from app.evaluation.execution.stages.stage import ExecutionStage, ValidationIssue
from app.evaluation.execution.stages.types import StageType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.context.context import PipelineContext
    from app.providers.contracts.chat import ChatProvider
    from app.providers.registry.registry import ProviderRegistry
    from app.providers.runtime.execution.runtime_coordinator import (
        ExecutionRequest,
        RuntimeCoordinator,
    )


class EvaluationPipelineExecutor(PipelineExecutor):
    """Executes an ExecutionPipeline by iterating through stages."""

    async def execute(
        self,
        pipeline: Any,
        context: PipelineContext,
    ) -> ExecutionResult:
        """Execute all stages in the pipeline sequentially."""
        start_time = time.monotonic()
        stage_results: list[StageResult] = []
        total_items = pipeline.plan.total_items if pipeline.plan else 0
        items_succeeded = 0
        items_failed = 0
        outcome = ExecutionOutcome.SUCCESS
        error_msg: str | None = None

        for stage in pipeline.stages:
            if context.is_cancelled:
                outcome = ExecutionOutcome.CANCELLED
                break

            stage_type = stage.stage_type
            steps = pipeline.plan.steps_for_stage(stage_type) if pipeline.plan else []

            try:
                result = await stage.execute(context, steps)
                stage_results.append(result)
                items_succeeded += result.items_succeeded
                items_failed += result.items_failed
            except Exception as exc:
                error_msg = str(exc)
                outcome = ExecutionOutcome.FAILURE
                stage_results.append(
                    StageResult(
                        stage_type=stage_type,
                        stage_name=stage.name,
                        outcome=ExecutionOutcome.FAILURE,
                        error=error_msg,
                        items_failed=1,
                        items_processed=1,
                    )
                )
                break

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        return ExecutionResult(
            run_id=context.run_id,
            outcome=outcome,
            stage_results=tuple(stage_results),
            total_duration_ms=elapsed_ms,
            total_items=total_items,
            items_processed=items_succeeded + items_failed,
            items_succeeded=items_succeeded,
            items_failed=items_failed,
            error=error_msg,
            completed_at=datetime.now(UTC),
        )


def _build_step_result(
    step: ExecutionStep,
    stage_type: StageType,
    status: StepStatus,
    outcome: ExecutionOutcome,
    duration_ms: int = 0,
    error: str | None = None,
    response: str = "",
) -> StepResult:
    """Build a StepResult with common fields."""
    metadata: dict[str, str] = {}
    if response:
        metadata["response"] = response
    return StepResult(
        step_id=step.step_id,
        step_name=step.name,
        stage_type=stage_type,
        status=status,
        outcome=outcome,
        duration_ms=duration_ms,
        error=error,
        metadata=metadata,
    )


def _make_placeholder(
    stage_type: StageType,
    stage_name: str,
) -> type[ExecutionStage]:
    """Create a lightweight placeholder ExecutionStage subclass."""

    class _Stage(ExecutionStage):
        def __init__(self) -> None:
            super().__init__(stage_type=stage_type, name=stage_name)

        def validate(self, context: PipelineContext) -> list[ValidationIssue]:
            return []

        async def execute(
            self,
            context: PipelineContext,
            steps: Sequence[ExecutionStep],
        ) -> StageResult:
            start = time.monotonic()
            results = [
                _build_step_result(s, stage_type, StepStatus.COMPLETED, ExecutionOutcome.SUCCESS)
                for s in steps
            ]
            elapsed = int((time.monotonic() - start) * 1000)
            return StageResult(
                stage_type=stage_type,
                stage_name=stage_name,
                outcome=ExecutionOutcome.SUCCESS,
                step_results=tuple(results),
                duration_ms=elapsed,
                items_processed=len(results),
                items_succeeded=len(results),
                completed_at=datetime.now(UTC),
            )

        async def rollback(self, context: PipelineContext, result: StageResult) -> None:
            pass

        def supports_resume(self) -> bool:
            return True

    return _Stage  # type: ignore[return-value]


class ProviderInvocationStage(ExecutionStage):
    """Stage that invokes the provider for each item via RuntimeCoordinator."""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        runtime_coordinator: RuntimeCoordinator,
    ) -> None:
        """Initialize with provider registry and runtime coordinator."""
        super().__init__(stage_type=StageType.PROVIDER_INVOCATION, name="Provider Invocation")
        self._provider_registry = provider_registry
        self._runtime_coordinator = runtime_coordinator

    def validate(self, context: PipelineContext) -> list[ValidationIssue]:
        """Validate provider availability."""
        issues: list[ValidationIssue] = []
        provider_name = context.provider_selection.provider_name
        if provider_name and not self._provider_registry.is_registered(provider_name):
            issues.append(
                ValidationIssue(
                    message=f"Provider '{provider_name}' not registered",
                    code="PROVIDER_NOT_FOUND",
                )
            )
        return issues

    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
    ) -> StageResult:
        """Execute provider invocations for all steps."""
        start = time.monotonic()
        step_results: list[StepResult] = []
        succeeded = 0
        failed = 0

        for step in steps:
            if context.is_cancelled:
                step_results.append(
                    _build_step_result(
                        step,
                        StageType.PROVIDER_INVOCATION,
                        StepStatus.SKIPPED,
                        ExecutionOutcome.CANCELLED,
                    )
                )
                continue

            result = await self._execute_step(context, step)
            step_results.append(result)
            if result.is_success:
                succeeded += 1
            else:
                failed += 1

        elapsed = int((time.monotonic() - start) * 1000)
        outcome = ExecutionOutcome.FAILURE if failed > 0 else ExecutionOutcome.SUCCESS

        return StageResult(
            stage_type=StageType.PROVIDER_INVOCATION,
            stage_name=self.name,
            outcome=outcome,
            step_results=tuple(step_results),
            duration_ms=elapsed,
            items_processed=succeeded + failed,
            items_succeeded=succeeded,
            items_failed=failed,
            completed_at=datetime.now(UTC),
        )

    async def rollback(
        self,
        context: PipelineContext,
        result: StageResult,
    ) -> None:
        """No rollback needed for provider invocations."""

    def supports_resume(self) -> bool:
        """Provider invocation supports resume via checkpoints."""
        return True

    async def _execute_step(
        self,
        context: PipelineContext,
        step: ExecutionStep,
    ) -> StepResult:
        """Execute a single provider invocation step."""
        step_start = time.monotonic()
        try:
            from app.providers.runtime.execution.runtime_coordinator import (
                ExecutionRequest,
            )

            request = ExecutionRequest(
                provider_name=context.provider_selection.provider_name,
                model_id=context.provider_selection.model_id,
                messages=[{"role": "user", "content": f"Item {step.item_index}"}],
                request_id=str(step.step_id),
                timeout_seconds=float(step.timeout_seconds or 60),
            )

            provider = self._provider_registry.resolve(
                context.provider_selection.provider_name,
            )

            async def _handler(req: ExecutionRequest) -> str:
                return await self._invoke_provider(provider, req)

            runtime_result = await self._runtime_coordinator.execute(request, _handler)
            elapsed = int((time.monotonic() - step_start) * 1000)

            if runtime_result.success:
                return _build_step_result(
                    step,
                    StageType.PROVIDER_INVOCATION,
                    StepStatus.COMPLETED,
                    ExecutionOutcome.SUCCESS,
                    elapsed,
                    response=runtime_result.response,
                )

            return _build_step_result(
                step,
                StageType.PROVIDER_INVOCATION,
                StepStatus.FAILED,
                ExecutionOutcome.FAILURE,
                elapsed,
                runtime_result.error,
            )

        except Exception as exc:
            elapsed = int((time.monotonic() - step_start) * 1000)
            return _build_step_result(
                step,
                StageType.PROVIDER_INVOCATION,
                StepStatus.FAILED,
                ExecutionOutcome.FAILURE,
                elapsed,
                str(exc),
            )

    async def _invoke_provider(
        self,
        provider: ChatProvider,
        request: ExecutionRequest,
    ) -> str:
        """Invoke the provider with proper Message objects."""
        from app.providers.models.messages import Message, TextContent

        messages = [
            Message(role="user", content=[TextContent(text=msg["content"])])
            for msg in request.messages
        ]

        response = await provider.chat(
            messages,
            model=request.model_id,
        )

        return response.content


MetricDispatchStage: type[ExecutionStage] = _make_placeholder(
    StageType.METRIC_DISPATCH,
    "Metric Dispatch",
)
AggregationStage: type[ExecutionStage] = _make_placeholder(
    StageType.AGGREGATION,
    "Aggregation",
)
PersistenceStage: type[ExecutionStage] = _make_placeholder(
    StageType.PERSISTENCE,
    "Persistence",
)
