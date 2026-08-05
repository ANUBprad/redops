"""EvaluationPlanner — concrete ExecutionPlanner implementation.

Transforms EvaluationRun configuration into a deterministic ExecutionPlan.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.execution.contracts.planner import ExecutionPlanner, PlanEstimate
from app.evaluation.execution.pipeline.plan import ExecutionPlan, PlanMetadata
from app.evaluation.execution.pipeline.step import ExecutionStep, StepDependency
from app.evaluation.execution.stages.types import StageType

if TYPE_CHECKING:
    from app.evaluation.data.dataset import DatasetItem
    from app.evaluation.data.store import DatasetStore
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun


_DEFAULT_STEP_TIMEOUT_SECONDS: int = 120
_SINGLE_EVALUATION_ROW_COUNT: int = 1


class EvaluationPlanner(ExecutionPlanner):
    """Creates ExecutionPlan instances from EvaluationRun configuration.

    The planner reads the run's eval_type, metrics, dataset size,
    and execution policy to produce a fully deterministic plan
    describing every step that must execute. When a dataset store
    is configured, real dataset items are resolved and their
    prompt/reference/context are embedded into step metadata so
    the plan is self-contained and reproducible.
    """

    def __init__(self, dataset_store: DatasetStore | None = None) -> None:
        """Initialize the planner.

        Args:
            dataset_store: Optional store used to resolve dataset
                items referenced by the run configuration.

        """
        self._dataset_store = dataset_store

    async def plan(self, run: EvaluationRun) -> ExecutionPlan:
        """Create an execution plan for the given run.

        Reads eval_type, metrics, dataset.row_count, and policy
        to build an ordered list of stages and steps.
        """
        items = await self._resolve_dataset_items(run)
        stages = self._determine_stages(run)
        steps = self._build_steps(run, items)
        total_items = self._resolve_row_count(run, items)

        return ExecutionPlan.create(
            run_id=run.id,
            stages=stages,
            steps=steps,
            total_items=total_items,
            metadata=PlanMetadata(
                created_by="evaluation_planner",
                description=f"Plan for {run.evaluation_name}",
            ),
        )

    async def validate_plan(self, plan: ExecutionPlan) -> list[str]:
        """Validate an execution plan for correctness."""
        errors: list[str] = []
        if not plan.stages:
            errors.append("Plan has no stages")
        if plan.total_items < 0:
            errors.append(f"Invalid total_items: {plan.total_items}")
        if plan.run_id is None:
            errors.append("Plan is missing run_id")
        if not plan.steps and plan.total_items > 0:
            errors.append("Plan has items but no steps")
        return errors

    async def estimate(self, run: EvaluationRun) -> PlanEstimate:
        """Provide a resource estimate for executing the run."""
        items = await self._resolve_dataset_items(run)
        total_items = self._resolve_row_count(run, items)
        metric_count = len(run.config.metrics)
        estimated_tokens = total_items * metric_count * _ESTIMATED_TOKENS_PER_STEP
        estimated_cost = estimated_tokens * _ESTIMATED_COST_PER_TOKEN
        estimated_duration = total_items * _ESTIMATED_SECONDS_PER_STEP

        return PlanEstimate(
            estimated_steps=total_items,
            estimated_duration_seconds=estimated_duration,
            estimated_cost_usd=estimated_cost,
            estimated_tokens=estimated_tokens,
        )

    def _determine_stages(self, run: EvaluationRun) -> tuple[StageType, ...]:
        """Determine the ordered stages for the run."""
        stages = [
            StageType.PROVIDER_INVOCATION,
            StageType.METRIC_DISPATCH,
            StageType.AGGREGATION,
            StageType.PERSISTENCE,
        ]
        if run.config.eval_type == EvaluationType.SINGLE:
            stages = [StageType.PROVIDER_INVOCATION, StageType.METRIC_DISPATCH]
        return tuple(stages)

    async def _resolve_dataset_items(self, run: EvaluationRun) -> tuple[DatasetItem, ...]:
        """Resolve dataset items from the configured store.

        Args:
            run: The run whose dataset reference is resolved.

        Returns:
            The dataset items, or an empty tuple when no dataset
            is configured or the store cannot resolve it.

        """
        if self._dataset_store is None or run.config.dataset is None:
            return ()
        try:
            dataset = await self._dataset_store.load(run.config.dataset.dataset_id)
        except KeyError:
            return ()
        return dataset.items

    def _build_steps(
        self,
        run: EvaluationRun,
        items: tuple[DatasetItem, ...],
    ) -> tuple[ExecutionStep, ...]:
        """Build execution steps for each dataset row.

        Args:
            run: The run to plan steps for.
            items: Resolved dataset items, empty when unavailable.

        Returns:
            Execution steps with real prompt/context/reference
            embedded in step metadata when items are available.

        """
        total_items = self._resolve_row_count(run, items)
        policy = run.config.policy
        steps: list[ExecutionStep] = []

        for idx in range(total_items):
            dependencies: list[StepDependency] = []
            if idx > 0:
                prev_step_id = steps[-1].step_id
                dependencies.append(StepDependency(step_id=prev_step_id))

            metadata: dict[str, str] = {}
            if idx < len(items):
                item = items[idx]
                metadata["prompt"] = item.prompt
                metadata["reference"] = item.reference or ""
                metadata["context"] = item.context or ""
                metadata["item_id"] = item.id or ""

            step = ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION,
                name=f"invoke_item_{idx}",
                item_index=idx,
                dependencies=dependencies,
                max_retries=policy.max_retries_per_item,
                timeout_seconds=policy.timeout_per_item_seconds or _DEFAULT_STEP_TIMEOUT_SECONDS,
                order=idx,
                metadata=metadata,
            )
            steps.append(step)

        return tuple(steps)

    def _resolve_row_count(
        self,
        run: EvaluationRun,
        items: tuple[DatasetItem, ...] = (),
    ) -> int:
        """Resolve the number of items in the dataset.

        Args:
            run: The run being planned.
            items: Resolved dataset items, empty when unavailable.

        Returns:
            The number of items to execute.

        """
        if items:
            return len(items)
        if run.config.dataset is not None:
            return run.config.dataset.row_count
        return _SINGLE_EVALUATION_ROW_COUNT


_ESTIMATED_TOKENS_PER_STEP: int = 500
_ESTIMATED_COST_PER_TOKEN: float = 0.000003
_ESTIMATED_SECONDS_PER_STEP: int = 2
