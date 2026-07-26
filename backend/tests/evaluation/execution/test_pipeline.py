"""Tests for the pipeline module."""

from __future__ import annotations

from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.stages.stage import ExecutionStage
from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7


class TestExecutionPipeline:
    """Tests for ExecutionPipeline."""

    def test_creation(self) -> None:
        """Verify basic pipeline creation."""
        pipeline = ExecutionPipeline()
        assert pipeline.pipeline_id is not None
        assert pipeline.plan is None
        assert pipeline.stages == ()
        assert pipeline.stage_count == 0

    def test_with_plan(self) -> None:
        """Verify pipeline with plan."""
        plan = ExecutionPlan.create(run_id=UUIDv7.generate())
        pipeline = ExecutionPipeline(plan=plan)
        assert pipeline.plan == plan
        assert pipeline.run_id == plan.run_id

    def test_with_stages(self) -> None:
        """Verify pipeline with stages."""
        stage1 = _TestStage(StageType.PLANNING, "Planning")
        stage2 = _TestStage(StageType.PREPARATION, "Prep")
        pipeline = ExecutionPipeline(
            stages=(stage1, stage2),
            stage_order=(StageType.PLANNING, StageType.PREPARATION),
        )
        assert pipeline.stage_count == 2
        assert pipeline.stage_types == [StageType.PLANNING, StageType.PREPARATION]

    def test_get_stage(self) -> None:
        """Verify stage lookup by type."""
        planning = _TestStage(StageType.PLANNING, "Planning")
        pipeline = ExecutionPipeline(
            stages=(planning,),
            stage_order=(StageType.PLANNING,),
        )
        found = pipeline.get_stage(StageType.PLANNING)
        assert found is planning
        assert pipeline.get_stage(StageType.PROVIDER_INVOCATION) is None

    def test_has_stage(self) -> None:
        """Verify has_stage check."""
        pipeline = ExecutionPipeline(
            stages=(_TestStage(StageType.PLANNING, "Planning"),),
            stage_order=(StageType.PLANNING,),
        )
        assert pipeline.has_stage(StageType.PLANNING)
        assert not pipeline.has_stage(StageType.COMPLETION)

    def test_stages_by_type(self) -> None:
        """Verify stages indexed by type."""
        planning = _TestStage(StageType.PLANNING, "Planning")
        prep = _TestStage(StageType.PREPARATION, "Prep")
        pipeline = ExecutionPipeline(
            stages=(planning, prep),
            stage_order=(StageType.PLANNING, StageType.PREPARATION),
        )
        index = pipeline.stages_by_type
        assert index[StageType.PLANNING] is planning
        assert index[StageType.PREPARATION] is prep

    def test_immutability(self) -> None:
        """Verify ExecutionPipeline is frozen."""
        pipeline = ExecutionPipeline()
        try:
            pipeline.pipeline_id = UUIDv7.generate()  # type: ignore
            assert False
        except AttributeError:
            pass


class _TestStage(ExecutionStage):
    """Concrete stage for pipeline testing."""

    def validate(self, context):  # type: ignore[no-untyped-def]
        return []

    async def execute(self, context, steps):  # type: ignore[no-untyped-def]
        from app.evaluation.execution.results.results import StageResult
        return StageResult(stage_type=self.stage_type, stage_name=self.name)

    async def rollback(self, context, result):  # type: ignore[no-untyped-def]
        pass

    def supports_resume(self) -> bool:
        return False
