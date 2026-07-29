"""PipelineBuilder — transforms an EvaluationRun into an executable pipeline.

The builder is the assembly point: it takes an EvaluationRun,
produces a validated ExecutionPlan, and then constructs an
ExecutionPipeline with concrete stage instances.

All invariants are enforced at build time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
from app.evaluation.execution.validators.validators import (
    DependencyGraphValidator,
    PlanValidator,
    StageOrderingValidator,
)
from app.kernel.exceptions.errors import ValidationError

if TYPE_CHECKING:
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
    from app.evaluation.execution.contracts.planner import ExecutionPlanner
    from app.evaluation.execution.pipeline.plan import ExecutionPlan
    from app.evaluation.execution.stages.stage import ExecutionStage


class PipelineBuildingError(ValidationError):
    """Raised when pipeline construction fails."""

    def __init__(
        self,
        message: str = "",
        *,
        reason: str = "",
        details: dict[str, str] | None = None,
    ) -> None:
        """Initialize PipelineBuildingError.

        Args:
            message: Error description.
            reason: Categorised reason for failure.
            details: Optional structured details.

        """
        self.reason = reason
        super().__init__(
            message or f"Pipeline building failed: {reason}",
            field="pipeline",
            details={**(details or {}), "reason": reason},
        )


class PipelineBuilder:
    """Builder that transforms EvaluationRun → ExecutionPlan → ExecutionPipeline.

    Usage:
        builder = PipelineBuilder(planner=my_planner, stages=[...])
        pipeline = await builder.build(run)
    """

    def __init__(
        self,
        planner: ExecutionPlanner,
        stages: list[ExecutionStage],
        *,
        auto_validate: bool = True,
    ) -> None:
        """Initialize the pipeline builder.

        Args:
            planner: The planner to use for plan creation.
            stages: Available stage implementations.
            auto_validate: If True, validate at each build step.

        """
        self._planner = planner
        self._stages = list(stages)
        self._auto_validate = auto_validate

    @property
    def planner(self) -> ExecutionPlanner:
        """Return the associated planner."""
        return self._planner

    @property
    def stages(self) -> list[ExecutionStage]:
        """Return the registered stage implementations."""
        return list(self._stages)

    async def build(self, run: EvaluationRun) -> ExecutionPipeline:
        """Build an execution pipeline from an evaluation run.

        The build process:
        1. Creates an ExecutionPlan using the planner
        2. Validates the plan structure
        3. Validates stage ordering
        4. Validates dependencies
        5. Assembles the ExecutionPipeline

        Args:
            run: The evaluation run to build for.

        Returns:
            A validated ExecutionPipeline ready for execution.

        Raises:
            PipelineBuildingError: If any validation step fails.

        """
        # Step 1: Create the plan
        plan = await self._planner.plan(run)

        # Step 2: Validate plan structure
        if self._auto_validate:
            plan_errors = await self._planner.validate_plan(plan)
            if plan_errors:
                msg = "; ".join(plan_errors)
                raise PipelineBuildingError(
                    message=msg,
                    reason="plan_validation_failed",
                    details={"errors": msg},
                )

            PlanValidator.validate_or_raise(plan)
            StageOrderingValidator.validate_or_raise(plan.stages)

            # Validate dependency graph if steps have dependencies
            steps_with_deps = [s for s in plan.steps if s.has_dependencies]
            if steps_with_deps:
                DependencyGraphValidator.validate_or_raise(plan.steps)

        # Step 3: Map plan stages to concrete stage implementations
        stage_map = {s.stage_type: s for s in self._stages}
        pipeline_stages: list[ExecutionStage] = []
        for stage_type in plan.stages:
            stage = stage_map.get(stage_type)
            if stage is None:
                msg = f"No stage implementation registered for {stage_type.value}"
                raise PipelineBuildingError(message=msg, reason="missing_stage")
            pipeline_stages.append(stage)

        # Step 4: Build and return the pipeline
        return ExecutionPipeline(
            plan=plan,
            stages=tuple(pipeline_stages),
            stage_order=plan.stages,
        )

    async def build_from_plan(self, plan: ExecutionPlan) -> ExecutionPipeline:
        """Build an execution pipeline from an existing plan.

        Args:
            plan: An already-validated execution plan.

        Returns:
            An ExecutionPipeline ready for execution.

        Raises:
            PipelineBuildingError: If stage implementations are missing.

        """
        if self._auto_validate:
            PlanValidator.validate_or_raise(plan)

        stage_map = {s.stage_type: s for s in self._stages}
        pipeline_stages: list[ExecutionStage] = []
        for stage_type in plan.stages:
            stage = stage_map.get(stage_type)
            if stage is None:
                msg = f"No stage implementation registered for {stage_type.value}"
                raise PipelineBuildingError(message=msg, reason="missing_stage")
            pipeline_stages.append(stage)

        return ExecutionPipeline(
            plan=plan,
            stages=tuple(pipeline_stages),
            stage_order=plan.stages,
        )
