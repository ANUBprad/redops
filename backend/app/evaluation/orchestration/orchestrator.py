"""EvaluationOrchestrator — the main orchestration entry point.

Coordinates the full lifecycle of an evaluation run: planning,
building, execution, checkpointing, state transitions, and event
publication.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.evaluation.domain.enums.evaluation_enums import (
    CancellationReason,
    RunStatus,
)
from app.evaluation.execution.context.context import (
    PipelineContext,
    TraceIdentifiers,
)
from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
from app.evaluation.execution.results.results import ExecutionOutcome, ExecutionResult
from app.evaluation.orchestration.checkpoint import CheckpointManager
from app.evaluation.orchestration.executor import (
    AggregationStage,
    EvaluationPipelineExecutor,
    MetricDispatchStage,
    PersistenceStage,
    ProviderInvocationStage,
)
from app.evaluation.orchestration.observer import EventPublishingObserver
from app.evaluation.orchestration.planner import EvaluationPlanner

if TYPE_CHECKING:
    from app.evaluation.data.store import DatasetStore
    from app.evaluation.domain.contracts.evaluation_contracts import (
        CheckpointRepository,
        EventPublisher,
        ItemRepository,
        RunRepository,
    )
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
    from app.evaluation.metrics.engine import MetricEngine
    from app.kernel.entities.base import UUIDv7
    from app.providers.cost.calculator import CostCalculator
    from app.providers.registry.registry import ProviderRegistry
    from app.providers.runtime.execution.runtime_coordinator import RuntimeCoordinator

logger = logging.getLogger(__name__)


class EvaluationOrchestrator:
    """Main orchestrator for evaluation run execution.

    Coordinates planning, building, executing, checkpointing,
    and state management throughout the run lifecycle.
    """

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        event_publisher: EventPublisher,
        run_repository: RunRepository,
        item_repository: ItemRepository,
        checkpoint_repository: CheckpointRepository,
        metric_engine: MetricEngine,
        runtime_coordinator: RuntimeCoordinator | None = None,
        metric_result_repository: Any | None = None,
        dataset_store: DatasetStore | None = None,
        cost_calculator: CostCalculator | None = None,
    ) -> None:
        """Initialize orchestrator with all required dependencies.

        Args:
            provider_registry: Registry used to resolve providers.
            event_publisher: Publisher for run lifecycle events.
            run_repository: Repository for evaluation runs.
            item_repository: Repository for dataset items.
            checkpoint_repository: Repository for checkpoints.
            metric_engine: Engine that evaluates metrics.
            runtime_coordinator: Optional runtime coordinator override.
            metric_result_repository: Optional metric result persistence.
            dataset_store: Optional store used to resolve dataset items.
            cost_calculator: Optional cost calculator for real cost estimates.

        """
        self._provider_registry = provider_registry
        self._event_publisher = event_publisher
        self._run_repository = run_repository
        self._item_repository = item_repository
        self._checkpoint_repository = checkpoint_repository
        self._metric_engine = metric_engine
        self._metric_result_repository = metric_result_repository

        self._planner = EvaluationPlanner(dataset_store=dataset_store)
        self._observer = EventPublishingObserver(event_publisher)
        self._checkpoint_manager = CheckpointManager()

        if runtime_coordinator is not None:
            self._runtime_coordinator = runtime_coordinator
        else:
            self._runtime_coordinator = _create_runtime_coordinator()

        if cost_calculator is not None:
            self._cost_calculator = cost_calculator
        else:
            from app.providers.cost.defaults import build_default_cost_calculator

            self._cost_calculator = build_default_cost_calculator()

        self._active_pipelines: dict[str, ExecutionPipeline] = {}
        self._active_contexts: dict[str, PipelineContext] = {}

    async def execute_run(self, run: EvaluationRun) -> ExecutionResult:
        """Execute a complete evaluation run."""
        run_id_str = str(run.id)

        if run.status == RunStatus.CREATED:
            run.queue()
            await self._run_repository.save(run)

        context = self._create_context(run)
        self._active_contexts[run_id_str] = context

        try:
            plan = await self._planner.plan(run)
            validation_errors = await self._planner.validate_plan(plan)
            if validation_errors:
                run.fail(
                    error_code="PLAN_VALIDATION_FAILED",
                    error_message="; ".join(validation_errors),
                )
                await self._run_repository.save(run)
                return self._build_error_result(run, validation_errors[0])

            pipeline = self._build_pipeline(plan)
            self._active_pipelines[run_id_str] = pipeline

            context_with_plan = PipelineContext(
                run_id=context.run_id,
                evaluation_name=context.evaluation_name,
                plan=plan,
                config=context.config,
                profile=context.profile,
                metadata=context.metadata,
                execution_context=context.execution_context,
                provider_selection=context.provider_selection,
                metric_selection=context.metric_selection,
                cancellation_token=context.cancellation_token,
                trace=context.trace,
            )

            run.start(plan.total_items)
            await self._run_repository.save(run)
            self._observer.set_run_id(run.id)
            await self._observer.on_execution_started(context_with_plan)

            executor = EvaluationPipelineExecutor()
            result = await executor.execute(pipeline, context_with_plan)

        except Exception as exc:
            logger.exception("Run execution failed")
            run.fail(
                error_code="EXECUTION_FAILED",
                error_message=str(exc),
            )
            await self._run_repository.save(run)
            return self._build_error_result(run, str(exc))
        else:
            await self._observer.on_execution_finished(result)
            await self._finalize_run(run, result)
            return result

        finally:
            self._active_pipelines.pop(run_id_str, None)
            self._active_contexts.pop(run_id_str, None)

    async def pause_run(self, run_id: UUIDv7) -> None:
        """Pause a running evaluation."""
        run = await self._run_repository.find_by_id(run_id)
        if run is None:
            msg = f"Run {run_id} not found"
            raise ValueError(msg)

        if run.status != RunStatus.RUNNING:
            msg = f"Cannot pause run in {run.status.value} state"
            raise ValueError(msg)

        run.pause()
        await self._run_repository.save(run)

    async def resume_run(self, run_id: UUIDv7) -> ExecutionResult:
        """Resume a paused evaluation run from its last checkpoint."""
        run = await self._run_repository.find_by_id(run_id)
        if run is None:
            msg = f"Run {run_id} not found"
            raise ValueError(msg)

        if run.status != RunStatus.PAUSED:
            msg = f"Cannot resume run in {run.status.value} state"
            raise ValueError(msg)

        checkpoint = await self._checkpoint_repository.find_latest(run_id)
        if checkpoint is None:
            msg = "No checkpoint available for resume"
            raise ValueError(msg)

        run.resume()
        await self._run_repository.save(run)

        return await self.execute_run(run)

    async def cancel_run(self, run_id: UUIDv7, *, force: bool = False) -> None:
        """Cancel a running evaluation."""
        run = await self._run_repository.find_by_id(run_id)
        if run is None:
            msg = f"Run {run_id} not found"
            raise ValueError(msg)

        if run.status.is_terminal:
            msg = f"Cannot cancel run in {run.status.value} state"
            raise ValueError(msg)

        reason = CancellationReason.USER_CANCELLED
        run.cancel(reason=reason, force=force)
        await self._run_repository.save(run)

        run_id_str = str(run_id)
        if force and run_id_str in self._active_contexts:
            ctx = self._active_contexts[run_id_str]
            self._active_contexts[run_id_str] = ctx.with_cancellation(force=True)

    def _create_context(self, run: EvaluationRun) -> PipelineContext:
        """Create a PipelineContext from an EvaluationRun."""
        trace = TraceIdentifiers.from_correlation_id(str(run.id))
        return PipelineContext.from_run(run, trace=trace)

    def _build_pipeline(
        self,
        plan: Any,
    ) -> ExecutionPipeline:
        """Build an ExecutionPipeline from a plan and real stages."""
        stages = [
            ProviderInvocationStage(
                self._provider_registry,
                self._runtime_coordinator,
                cost_calculator=self._cost_calculator,
            ),
            MetricDispatchStage(
                self._metric_engine,
                provider_registry=self._provider_registry,
            ),
            AggregationStage(self._metric_engine),
            PersistenceStage(
                metric_result_repository=getattr(self, "_metric_result_repository", None),
                run_repository=self._run_repository,
            ),
        ]

        stage_map = {s.stage_type: s for s in stages}
        pipeline_stages = []
        for st in plan.stages:
            if st in stage_map:
                pipeline_stages.append(stage_map[st])
            else:
                raise ValueError(f"No implementation for stage {st.value}")

        return ExecutionPipeline(
            plan=plan,
            stages=tuple(pipeline_stages),
            stage_order=plan.stages,
        )

    async def _finalize_run(
        self,
        run: EvaluationRun,
        result: ExecutionResult,
    ) -> None:
        """Finalize run state based on execution result."""
        if result.outcome == ExecutionOutcome.SUCCESS:
            run.items_completed = result.items_succeeded
            run.complete()
        elif result.outcome == ExecutionOutcome.CANCELLED:
            pass
        else:
            run.items_completed = result.items_succeeded
            run.fail(
                error_code="EXECUTION_FAILED",
                error_message=result.error or "Execution completed with failures",
            )

        await self._run_repository.save(run)

    def _build_error_result(self, run: EvaluationRun, error: str) -> ExecutionResult:
        """Build an error ExecutionResult."""
        return ExecutionResult(
            run_id=run.id,
            outcome=ExecutionOutcome.FAILURE,
            total_items=run.items_total,
            error=error,
        )


def _create_runtime_coordinator() -> Any:
    """Create a RuntimeCoordinator for provider invocations."""
    from app.providers.runtime.execution.runtime_coordinator import (
        RuntimeCoordinator,
    )

    return RuntimeCoordinator()
