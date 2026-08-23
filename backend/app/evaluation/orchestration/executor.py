"""EvaluationPipelineExecutor and stage executors.

Contains the real implementations of MetricDispatch, Aggregation,
and Persistence stages that actually execute metrics, compute
aggregations, and persist results.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.evaluation.execution.contracts.executor import PipelineExecutor
from app.evaluation.execution.pipeline.step import ExecutionStep, StepStatus
from app.evaluation.execution.prompt_builder import PromptTemplate
from app.evaluation.execution.results.results import (
    ExecutionOutcome,
    ExecutionResult,
    StageResult,
    StepResult,
)
from app.evaluation.execution.stages.stage import ExecutionStage, ValidationIssue
from app.evaluation.execution.stages.types import StageType
from app.evaluation.metrics.domain import MetricInput, MetricResult
from app.evaluation.metrics.engine import MetricEngine
from app.providers.cost.calculator import CostCalculator
from app.providers.cost.defaults import build_default_cost_calculator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.metrics.domain import MetricAggregation
    from app.providers.contracts.base import BaseProvider
    from app.providers.contracts.chat import ChatProvider
    from app.providers.registry.registry import ProviderRegistry
    from app.providers.runtime.execution.runtime_coordinator import RuntimeCoordinator

logger = logging.getLogger(__name__)

_EXECUTION_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "model",
        "request_id",
        "tokens_input",
        "tokens_output",
        "tokens_cached",
        "cost_usd",
        "cost_estimated",
        "latency_ms",
        "finish_reason",
    }
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

        shared_state: dict[str, Any] = {}

        for stage in pipeline.stages:
            if context.is_cancelled:
                outcome = ExecutionOutcome.CANCELLED
                break

            stage_type = stage.stage_type
            steps = pipeline.plan.steps_for_stage(stage_type) if pipeline.plan else []

            try:
                result = await stage.execute(context, steps, shared_state=shared_state)
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
    metadata: dict[str, str] | None = None,
) -> StepResult:
    """Build a StepResult with common fields."""
    result_metadata: dict[str, str] = metadata or {}
    if response:
        result_metadata["response"] = response
    return StepResult(
        step_id=step.step_id,
        step_name=step.name,
        stage_type=stage_type,
        status=status,
        outcome=outcome,
        duration_ms=duration_ms,
        error=error,
        metadata=result_metadata,
    )


class ProviderInvocationStage(ExecutionStage):
    """Stage that invokes the provider for each item via RuntimeCoordinator."""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        runtime_coordinator: RuntimeCoordinator,
        *,
        cost_calculator: CostCalculator | None = None,
    ) -> None:
        super().__init__(stage_type=StageType.PROVIDER_INVOCATION, name="Provider Invocation")
        self._provider_registry = provider_registry
        self._runtime_coordinator = runtime_coordinator
        self._cost_calculator = cost_calculator or build_default_cost_calculator()

    def validate(self, context: PipelineContext) -> list[ValidationIssue]:
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
        shared_state: dict[str, Any] | None = None,
    ) -> StageResult:
        start = time.monotonic()
        step_results: list[StepResult] = []
        succeeded = 0
        failed = 0
        provider_responses: dict[int, str] = {}
        item_executions: dict[int, dict[str, str]] = {}

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
                if step.item_index is not None:
                    provider_responses[step.item_index] = result.metadata.get("response", "")
                    item_executions[step.item_index] = {
                        key: value
                        for key, value in result.metadata.items()
                        if key in _EXECUTION_METADATA_KEYS
                    }
            else:
                failed += 1

        if shared_state is not None:
            shared_state["provider_responses"] = provider_responses
            shared_state["item_executions"] = item_executions

        elapsed = int((time.monotonic() - start) * 1000)
        outcome = (
            ExecutionOutcome.FAILURE if failed > 0 and succeeded == 0 else ExecutionOutcome.SUCCESS
        )

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

    async def rollback(self, context: PipelineContext, result: StageResult) -> None:
        pass

    def supports_resume(self) -> bool:
        return True

    def _prompt_template_for(self, context: PipelineContext) -> PromptTemplate:
        """Build the prompt template from the run configuration.

        Args:
            context: The pipeline context.

        Returns:
            A PromptTemplate using the configured template and system prompt.

        """
        template = context.config.prompt_template if context.config else None
        system_prompt = context.profile.system_prompt if context.profile else None
        return PromptTemplate(
            template=template or "{prompt}",
            system_prompt=system_prompt,
        )

    def _build_request(
        self,
        context: PipelineContext,
        step: ExecutionStep,
    ) -> Any:
        """Build an ExecutionRequest with real item content.

        Args:
            context: The pipeline context.
            step: The step whose metadata carries item content.

        Returns:
            An ExecutionRequest with rendered system/user messages.

        """
        from app.providers.runtime.execution.runtime_coordinator import (
            ExecutionRequest,
        )

        prompt = step.metadata.get("prompt", "") or f"Item {step.item_index}"
        variables = {
            "prompt": prompt,
            "reference": step.metadata.get("reference", ""),
            "context": step.metadata.get("context", ""),
            "id": step.metadata.get("item_id", ""),
        }
        template = self._prompt_template_for(context)
        messages: list[dict[str, str]] = []
        if template.system_prompt:
            messages.append({"role": "system", "content": template.system_prompt})
        messages.append({"role": "user", "content": template.render_variables(variables)})

        return ExecutionRequest(
            provider_name=context.provider_selection.provider_name,
            model_id=context.provider_selection.model_id,
            messages=messages,
            request_id=str(step.step_id),
            timeout_seconds=float(step.timeout_seconds or 60),
        )

    async def _execute_step(
        self,
        context: PipelineContext,
        step: ExecutionStep,
    ) -> StepResult:
        step_start = time.monotonic()
        captured: dict[str, Any] = {}
        try:
            request = self._build_request(context, step)

            provider = self._provider_registry.resolve(
                context.provider_selection.provider_name,
            )

            async def _handler(req: Any) -> str:
                from app.providers.models.responses import ChatResponse

                response: ChatResponse = await self._invoke_provider(provider, req)
                captured["chat_response"] = response
                return response.content

            runtime_result = await self._runtime_coordinator.execute(request, _handler)
            elapsed = int((time.monotonic() - step_start) * 1000)

            if runtime_result.success:
                metadata = self._build_execution_metadata(
                    context,
                    step,
                    captured,
                    elapsed,
                )
                return _build_step_result(
                    step,
                    StageType.PROVIDER_INVOCATION,
                    StepStatus.COMPLETED,
                    ExecutionOutcome.SUCCESS,
                    elapsed,
                    response=runtime_result.response,
                    metadata=metadata,
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

    def _build_execution_metadata(
        self,
        context: PipelineContext,
        step: ExecutionStep,
        captured: dict[str, Any],
        latency_ms: int,
    ) -> dict[str, str]:
        """Build step metadata carrying real usage, cost, and latency.

        Args:
            context: The pipeline context.
            step: The executed step.
            captured: ChatResponse captured by the invocation handler.
            latency_ms: Measured invocation latency in milliseconds.

        Returns:
            A string-keyed metadata dict consumed by metric dispatch.

        """
        metadata: dict[str, str] = {}
        chat_response = captured.get("chat_response")
        if chat_response is None:
            return metadata

        usage = getattr(chat_response, "usage", None)
        tokens_input = getattr(usage, "input_tokens", 0) if usage is not None else 0
        tokens_output = getattr(usage, "output_tokens", 0) if usage is not None else 0
        tokens_cached = getattr(usage, "cached_tokens", 0) if usage is not None else 0

        cost_usd = 0.0
        cost_estimated = True
        try:
            from app.providers.tokenization.usage import TokenUsage

            cost_usd = self._cost_calculator.estimate_cost(
                context.provider_selection.provider_name,
                context.provider_selection.model_id,
                TokenUsage(
                    input_tokens=tokens_input,
                    output_tokens=tokens_output,
                    cached_tokens=tokens_cached,
                ),
            )
        except KeyError:
            cost_estimated = False

        model_id = getattr(chat_response, "model", "") or context.provider_selection.model_id
        request_id = getattr(chat_response, "request_id", None) or ""
        finish_reason = getattr(chat_response, "finish_reason", None)
        finish_reason_value = (
            getattr(finish_reason, "value", "") if finish_reason is not None else ""
        )

        metadata["model"] = model_id
        metadata["request_id"] = str(request_id)
        metadata["tokens_input"] = str(tokens_input)
        metadata["tokens_output"] = str(tokens_output)
        metadata["tokens_cached"] = str(tokens_cached)
        metadata["cost_usd"] = f"{max(cost_usd, 0.0):.6f}"
        metadata["cost_estimated"] = "true" if cost_estimated else "false"
        metadata["latency_ms"] = str(latency_ms)
        metadata["finish_reason"] = finish_reason_value
        metadata["prompt"] = step.metadata.get("prompt", "")
        metadata["reference"] = step.metadata.get("reference", "")
        metadata["context"] = step.metadata.get("context", "")
        return metadata

    async def _invoke_provider(
        self,
        provider: BaseProvider,
        request: Any,
    ) -> Any:
        from app.providers.models.enums import MessageRole
        from app.providers.models.messages import Message, TextContent

        chat_provider: ChatProvider = provider  # type: ignore[assignment]

        role_map: dict[str, MessageRole] = {
            "system": MessageRole.SYSTEM,
            "user": MessageRole.USER,
            "assistant": MessageRole.ASSISTANT,
            "tool": MessageRole.TOOL,
        }
        messages = [
            Message(
                role=role_map.get(msg.get("role", "user"), MessageRole.USER),
                content=[TextContent(text=msg["content"])],
            )
            for msg in request.messages
        ]

        response = await chat_provider.chat(
            messages,
            model=request.model_id,
        )

        return response


class MetricDispatchStage(ExecutionStage):
    """Stage that runs metrics against provider responses."""

    def __init__(
        self,
        metric_engine: MetricEngine,
        *,
        provider_registry: ProviderRegistry | None = None,
    ) -> None:
        super().__init__(stage_type=StageType.METRIC_DISPATCH, name="Metric Dispatch")
        self._metric_engine = metric_engine
        self._provider_registry = provider_registry

    def validate(self, context: PipelineContext) -> list[ValidationIssue]:
        return []

    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
        shared_state: dict[str, Any] | None = None,
    ) -> StageResult:
        start = time.monotonic()
        step_results: list[StepResult] = []
        succeeded = 0
        failed = 0

        provider_responses: dict[int, str] = (shared_state or {}).get("provider_responses", {})
        item_executions: dict[int, dict[str, str]] = (shared_state or {}).get("item_executions", {})
        metric_names = context.metric_selection.metric_names

        for step in steps:
            if context.is_cancelled:
                step_results.append(
                    _build_step_result(
                        step,
                        StageType.METRIC_DISPATCH,
                        StepStatus.SKIPPED,
                        ExecutionOutcome.CANCELLED,
                    )
                )
                continue

            item_index = step.item_index or 0
            response_text = provider_responses.get(item_index, "")

            step_start = time.monotonic()
            try:
                input_data = MetricInput(
                    prompt=step.metadata.get("prompt", ""),
                    response=response_text,
                    reference=step.metadata.get("reference", ""),
                    context=step.metadata.get("context", ""),
                    metadata=self._build_metric_metadata(
                        context,
                        step,
                        item_index,
                        item_executions,
                    ),
                )

                results: list[MetricResult] = []
                resolved = self._metric_engine.resolve_metrics(metric_names)
                for metric_name in resolved:
                    try:
                        result = await self._metric_engine.evaluate_single(metric_name, input_data)
                        results.append(result)
                    except Exception as exc:
                        results.append(
                            MetricResult(
                                metric_name=metric_name,
                                score=0.0,
                                normalized_score=0.0,
                                error=str(exc),
                            )
                        )

                if shared_state is not None:
                    if "metric_results" not in shared_state:
                        shared_state["metric_results"] = {}
                    shared_state["metric_results"][item_index] = results

                elapsed = int((time.monotonic() - step_start) * 1000)
                step_results.append(
                    _build_step_result(
                        step,
                        StageType.METRIC_DISPATCH,
                        StepStatus.COMPLETED,
                        ExecutionOutcome.SUCCESS,
                        elapsed,
                        metadata={"metrics_evaluated": str(len(results))},
                    )
                )
                succeeded += 1

            except Exception as exc:
                elapsed = int((time.monotonic() - step_start) * 1000)
                step_results.append(
                    _build_step_result(
                        step,
                        StageType.METRIC_DISPATCH,
                        StepStatus.FAILED,
                        ExecutionOutcome.FAILURE,
                        elapsed,
                        str(exc),
                    )
                )
                failed += 1

        elapsed = int((time.monotonic() - start) * 1000)
        outcome = (
            ExecutionOutcome.FAILURE if failed > 0 and succeeded == 0 else ExecutionOutcome.SUCCESS
        )

        return StageResult(
            stage_type=StageType.METRIC_DISPATCH,
            stage_name=self.name,
            outcome=outcome,
            step_results=tuple(step_results),
            duration_ms=elapsed,
            items_processed=succeeded + failed,
            items_succeeded=succeeded,
            items_failed=failed,
            completed_at=datetime.now(UTC),
        )

    def _build_metric_metadata(
        self,
        context: PipelineContext,
        step: ExecutionStep,
        item_index: int,
        item_executions: dict[int, dict[str, str]],
    ) -> dict[str, Any]:
        """Build MetricInput metadata from execution and judge config.

        Args:
            context: The pipeline context.
            step: The executed step.
            item_index: The zero-based item index.
            item_executions: Real token/cost/latency data from the
                provider invocation stage, keyed by item index.

        Returns:
            Metadata consumed by metric implementations.

        """
        metadata: dict[str, Any] = {}
        metadata.update(item_executions.get(item_index, {}))
        metadata.update(step.metadata if step.metadata else {})

        judge_provider_name = context.metadata.judge_provider if context.metadata else None
        judge_model = context.metadata.judge_model if context.metadata else ""

        judge_provider = None
        if judge_provider_name and self._provider_registry is not None:
            judge_provider = self._provider_registry.resolve(judge_provider_name)

        metadata["_judge_provider"] = judge_provider
        metadata["_judge_provider_name"] = judge_provider_name or ""
        metadata["_judge_model"] = judge_model
        return metadata

    async def rollback(self, context: PipelineContext, result: StageResult) -> None:
        pass

    def supports_resume(self) -> bool:
        return True


class AggregationStage(ExecutionStage):
    """Stage that computes aggregated metric scores."""

    def __init__(self, metric_engine: MetricEngine) -> None:
        super().__init__(stage_type=StageType.AGGREGATION, name="Aggregation")
        self._metric_engine = metric_engine

    def validate(self, context: PipelineContext) -> list[ValidationIssue]:
        return []

    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
        shared_state: dict[str, Any] | None = None,
    ) -> StageResult:
        start = time.monotonic()

        metric_results_by_item: dict[int, list[MetricResult]] = (shared_state or {}).get(
            "metric_results", {}
        )

        aggregations: dict[str, MetricAggregation] = {}
        metric_names = set()

        for item_results in metric_results_by_item.values():
            for result in item_results:
                metric_names.add(result.metric_name)

        for metric_name in metric_names:
            all_results: list[MetricResult] = []
            for item_index in sorted(metric_results_by_item.keys()):
                for result in metric_results_by_item[item_index]:
                    if result.metric_name == metric_name:
                        all_results.append(result)

            if all_results:
                aggregation = self._metric_engine.aggregate(metric_name, tuple(all_results))
                aggregations[metric_name] = aggregation

        if shared_state is not None:
            shared_state["aggregations"] = aggregations

        elapsed = int((time.monotonic() - start) * 1000)

        return StageResult(
            stage_type=StageType.AGGREGATION,
            stage_name=self.name,
            outcome=ExecutionOutcome.SUCCESS,
            duration_ms=elapsed,
            items_processed=len(aggregations),
            items_succeeded=len(aggregations),
            completed_at=datetime.now(UTC),
        )

    async def rollback(self, context: PipelineContext, result: StageResult) -> None:
        pass

    def supports_resume(self) -> bool:
        return True


class PersistenceStage(ExecutionStage):
    """Stage that persists results to the database."""

    def __init__(
        self,
        metric_result_repository: Any | None = None,
        run_repository: Any | None = None,
        run_event_repository: Any | None = None,
    ) -> None:
        super().__init__(stage_type=StageType.PERSISTENCE, name="Persistence")
        self._metric_result_repo = metric_result_repository
        self._run_repo = run_repository
        self._run_event_repo = run_event_repository

    def validate(self, context: PipelineContext) -> list[ValidationIssue]:
        return []

    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
        shared_state: dict[str, Any] | None = None,
    ) -> StageResult:
        start = time.monotonic()

        metric_results_by_item: dict[int, list[MetricResult]] = (shared_state or {}).get(
            "metric_results", {}
        )

        persisted_count = 0
        if self._metric_result_repo is not None:
            for item_index, results in metric_results_by_item.items():
                try:
                    domain_results = [
                        MetricResult(
                            metric_name=result.metric_name,
                            score=result.score,
                            normalized_score=result.normalized_score,
                            raw_output=result.raw_output,
                            reasoning=result.reasoning,
                            metadata={
                                **result.metadata,
                                "run_id": str(context.run_id),
                                "item_id": result.metadata.get("item_id", str(item_index)),
                            },
                            execution_time_ms=result.execution_time_ms,
                            error=result.error,
                            confidence=result.confidence,
                            version=result.version,
                            cost_usd=result.cost_usd,
                        )
                        for result in results
                    ]
                    await self._metric_result_repo.save_many(domain_results)
                    persisted_count += len(domain_results)
                except Exception:
                    logger.exception(
                        "Failed to persist metric results for item_index=%s",
                        item_index,
                    )

        elapsed = int((time.monotonic() - start) * 1000)

        return StageResult(
            stage_type=StageType.PERSISTENCE,
            stage_name=self.name,
            outcome=ExecutionOutcome.SUCCESS,
            duration_ms=elapsed,
            items_processed=persisted_count,
            items_succeeded=persisted_count,
            completed_at=datetime.now(UTC),
        )

    async def rollback(self, context: PipelineContext, result: StageResult) -> None:
        pass

    def supports_resume(self) -> bool:
        return True
