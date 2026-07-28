"""Tests for the builder module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from app.evaluation.execution.builders.builder import PipelineBuilder, PipelineBuildingError
from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
from app.evaluation.execution.stages.stage import ExecutionStage
from app.evaluation.execution.stages.types import StageType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.step import ExecutionStep
    from app.evaluation.execution.results.results import StageResult


class TestPipelineBuilder:
    """Tests for PipelineBuilder."""

    async def test_build_success(self) -> None:
        """Verify successful pipeline build."""
        planner = _MockPlanner()
        stages = [
            _ConcreteStage(StageType.PLANNING, "Planning"),
            _ConcreteStage(StageType.PREPARATION, "Prep"),
        ]
        builder = PipelineBuilder(planner=planner, stages=stages)
        run = _MockRun()
        pipeline = await builder.build(run)  # type: ignore[arg-type]
        assert isinstance(pipeline, ExecutionPipeline)
        assert pipeline.stage_count == 2
        assert pipeline.has_stage(StageType.PLANNING)
        assert pipeline.has_stage(StageType.PREPARATION)

    async def test_build_with_missing_stage(self) -> None:
        """Verify build fails when stage implementation is missing."""
        planner = _MockPlanner()
        stages = [
            _ConcreteStage(StageType.PLANNING, "Planning"),
        ]
        builder = PipelineBuilder(planner=planner, stages=stages)
        run = _MockRun()
        with pytest.raises(PipelineBuildingError) as exc:
            await builder.build(run)  # type: ignore[arg-type]
        assert "No stage implementation registered" in str(exc.value)

    async def test_build_from_plan(self) -> None:
        """Verify build_from_plan works."""
        planner = _MockPlanner()
        stages = [
            _ConcreteStage(StageType.PLANNING, "Planning"),
            _ConcreteStage(StageType.PREPARATION, "Prep"),
        ]
        plan = await planner.plan(None)  # type: ignore[arg-type]
        builder = PipelineBuilder(planner=planner, stages=stages)
        pipeline = await builder.build_from_plan(plan)
        assert isinstance(pipeline, ExecutionPipeline)
        assert pipeline.stage_count == 2

    async def test_build_from_plan_missing_stage(self) -> None:
        """Verify build_from_plan fails when stage is missing."""
        planner = _MockPlanner()
        builder = PipelineBuilder(planner=planner, stages=[])
        plan = await planner.plan(None)  # type: ignore[arg-type]
        with pytest.raises(PipelineBuildingError):
            await builder.build_from_plan(plan)

    def test_stages_property(self) -> None:
        """Verify stages property returns registered stages."""
        planner = _MockPlanner()
        stages = [_ConcreteStage(StageType.PLANNING, "P")]
        builder = PipelineBuilder(planner=planner, stages=stages)
        assert len(builder.stages) == 1
        assert builder.stages[0].name == "P"

    def test_planner_property(self) -> None:
        """Verify planner property returns associated planner."""
        planner = _MockPlanner()
        builder = PipelineBuilder(planner=planner, stages=[])
        assert builder.planner is planner


class _MockPlanner:
    """Mock planner for testing."""

    async def plan(self, run):  # type: ignore[no-untyped-def]
        from app.evaluation.execution.pipeline.plan import ExecutionPlan
        from app.evaluation.execution.pipeline.step import ExecutionStep
        from app.kernel.entities.base import UUIDv7

        return ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING, StageType.PREPARATION],
            steps=[
                ExecutionStep.create(StageType.PLANNING, "plan-step"),
                ExecutionStep.create(StageType.PREPARATION, "prep-step"),
            ],
        )

    async def validate_plan(self, plan):  # type: ignore[no-untyped-def]
        return []

    async def estimate(self, run):  # type: ignore[no-untyped-def]
        from app.evaluation.execution.contracts.planner import PlanEstimate
        return PlanEstimate()


class _MockRun:
    """Mock evaluation run for testing."""
    pass


class _ConcreteStage(ExecutionStage):
    """Concrete stage for testing."""

    def validate(self, context: PipelineContext) -> list:
        return []

    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
    ) -> StageResult:
        from app.evaluation.execution.results.results import StageResult
        return StageResult(stage_type=self.stage_type, stage_name=self.name)

    async def rollback(self, context: PipelineContext, result: StageResult) -> None:
        pass

    def supports_resume(self) -> bool:
        return False
