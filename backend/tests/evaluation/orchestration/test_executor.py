"""Tests for EvaluationPipelineExecutor, ProviderInvocationStage, and placeholder stages."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.pipeline.step import ExecutionStep, StepStatus
from app.evaluation.execution.results.results import ExecutionOutcome, StageResult
from app.evaluation.execution.stages.types import StageType
from app.evaluation.orchestration.executor import (
    AggregationStage,
    EvaluationPipelineExecutor,
    MetricDispatchStage,
    PersistenceStage,
    ProviderInvocationStage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plan(
    total_items: int = 3, stage_type: StageType = StageType.PROVIDER_INVOCATION
) -> ExecutionPlan:
    """Build a minimal ExecutionPlan."""
    steps = [
        ExecutionStep.create(
            stage_type=stage_type,
            name=f"step_{i}",
            item_index=i,
            order=i,
        )
        for i in range(total_items)
    ]
    return ExecutionPlan.create(
        run_id=MagicMock(),
        stages=(stage_type,),
        steps=steps,
        total_items=total_items,
    )


def _make_pipeline(plan: ExecutionPlan | None = None, stage_cls=None) -> ExecutionPipeline:
    """Build a minimal pipeline with given stage class."""
    plan = plan or _make_plan()
    cls = stage_cls or MetricDispatchStage
    return ExecutionPipeline(
        plan=plan,
        stages=(cls(),),
        stage_order=(plan.stages[0] if plan.stages else StageType.METRIC_DISPATCH,),
    )


# ---------------------------------------------------------------------------
# EvaluationPipelineExecutor
# ---------------------------------------------------------------------------


class TestEvaluationPipelineExecutor:
    """Tests for EvaluationPipelineExecutor.execute()."""

    async def test_execute_success(self, sample_context) -> None:
        """Pipeline with passing stage should return SUCCESS."""
        plan = _make_plan(2, StageType.METRIC_DISPATCH)
        pipeline = _make_pipeline(plan, MetricDispatchStage)
        executor = EvaluationPipelineExecutor()
        result = await executor.execute(pipeline, sample_context)
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 2

    async def test_execute_respects_cancellation(self, cancelled_context) -> None:
        """Cancelled context should stop execution early."""
        plan = _make_plan(5, StageType.METRIC_DISPATCH)
        pipeline = _make_pipeline(plan, MetricDispatchStage)
        executor = EvaluationPipelineExecutor()
        result = await executor.execute(pipeline, cancelled_context)
        assert result.outcome == ExecutionOutcome.CANCELLED
        assert result.items_succeeded == 0

    async def test_execute_stage_exception_returns_failure(self, sample_context) -> None:
        """Stage raising an exception should return FAILURE."""
        plan = _make_plan(2)
        bad_stage = MagicMock()
        bad_stage.stage_type = StageType.PROVIDER_INVOCATION
        bad_stage.execute = AsyncMock(side_effect=RuntimeError("boom"))

        pipeline = ExecutionPipeline(
            plan=plan,
            stages=(bad_stage,),
            stage_order=(StageType.PROVIDER_INVOCATION,),
        )
        executor = EvaluationPipelineExecutor()
        result = await executor.execute(pipeline, sample_context)
        assert result.outcome == ExecutionOutcome.FAILURE
        assert "boom" in (result.error or "")

    async def test_execute_no_plan(self, sample_context) -> None:
        """Pipeline with no plan should use total_items=0."""
        pipeline = ExecutionPipeline(plan=None, stages=(), stage_order=())
        executor = EvaluationPipelineExecutor()
        result = await executor.execute(pipeline, sample_context)
        assert result.total_items == 0

    async def test_execute_multiple_stages(self, sample_context) -> None:
        """Multiple stages should all execute in order."""
        plan = _make_plan(1)
        s1 = MagicMock()
        s1.stage_type = StageType.PROVIDER_INVOCATION
        s1.execute = AsyncMock(
            return_value=StageResult(
                stage_type=StageType.PROVIDER_INVOCATION,
                stage_name="S1",
                outcome=ExecutionOutcome.SUCCESS,
                items_succeeded=1,
            )
        )
        s2 = MagicMock()
        s2.stage_type = StageType.METRIC_DISPATCH
        s2.execute = AsyncMock(
            return_value=StageResult(
                stage_type=StageType.METRIC_DISPATCH,
                stage_name="S2",
                outcome=ExecutionOutcome.SUCCESS,
                items_succeeded=1,
            )
        )
        pipeline = ExecutionPipeline(
            plan=plan,
            stages=(s1, s2),
            stage_order=(StageType.PROVIDER_INVOCATION, StageType.METRIC_DISPATCH),
        )
        executor = EvaluationPipelineExecutor()
        result = await executor.execute(pipeline, sample_context)
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert len(result.stage_results) == 2

    async def test_execute_stops_after_failure(self, sample_context) -> None:
        """Execution should stop after the first failing stage."""
        plan = _make_plan(2)
        good_stage = MagicMock()
        good_stage.stage_type = StageType.PROVIDER_INVOCATION
        good_stage.execute = AsyncMock(
            return_value=StageResult(
                stage_type=StageType.PROVIDER_INVOCATION,
                stage_name="Good",
                outcome=ExecutionOutcome.SUCCESS,
                items_succeeded=2,
            )
        )
        bad_stage = MagicMock()
        bad_stage.stage_type = StageType.METRIC_DISPATCH
        bad_stage.execute = AsyncMock(side_effect=RuntimeError("fail"))

        pipeline = ExecutionPipeline(
            plan=plan,
            stages=(good_stage, bad_stage),
            stage_order=(StageType.PROVIDER_INVOCATION, StageType.METRIC_DISPATCH),
        )
        executor = EvaluationPipelineExecutor()
        result = await executor.execute(pipeline, sample_context)
        assert result.outcome == ExecutionOutcome.FAILURE
        assert len(result.stage_results) == 2


# ---------------------------------------------------------------------------
# ProviderInvocationStage
# ---------------------------------------------------------------------------


class TestProviderInvocationStage:
    """Tests for ProviderInvocationStage."""

    def _make_stage(self, registry=None):
        if registry is not None:
            reg = registry
        else:
            reg = MagicMock()
            reg.is_registered.return_value = True
        coord = MagicMock()
        coord.execute = AsyncMock()
        return ProviderInvocationStage(reg, coord)

    def test_validate_registered_provider(self, sample_context) -> None:
        """Registered provider should produce no issues."""
        stage = self._make_stage()
        issues = stage.validate(sample_context)
        assert issues == []

    def test_validate_unregistered_provider(self, sample_context) -> None:
        """Unregistered provider should produce a validation issue."""
        reg = MagicMock()
        reg.is_registered.return_value = False
        stage = self._make_stage(registry=reg)
        issues = stage.validate(sample_context)
        assert len(issues) == 1
        assert issues[0].code == "PROVIDER_NOT_FOUND"

    def test_validate_empty_provider_name(self, sample_context) -> None:
        """Empty provider name should produce no issues (nothing to check)."""
        from app.evaluation.execution.context.context import PipelineContext, ProviderSelection

        ctx = PipelineContext(
            run_id=sample_context.run_id,
            provider_selection=ProviderSelection(provider_name="", model_id="m"),
        )
        stage = self._make_stage()
        issues = stage.validate(ctx)
        assert issues == []

    def test_supports_resume(self) -> None:
        """Stage should support resume."""
        stage = self._make_stage()
        assert stage.supports_resume() is True

    async def test_execute_steps_success(self, sample_context) -> None:
        """Successful provider invocation should produce SUCCESS results."""
        coord = MagicMock()

        class FakeResult:
            success = True
            error = None
            response = "Hello from provider"

        coord.execute = AsyncMock(return_value=FakeResult())
        stage = self._make_stage()
        stage._runtime_coordinator = coord

        steps = [
            ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION, name="s0", item_index=0, order=0
            ),
            ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION, name="s1", item_index=1, order=1
            ),
        ]
        result = await stage.execute(sample_context, steps)
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 2
        assert result.items_failed == 0

    async def test_execute_step_failure(self, sample_context) -> None:
        """Failed provider invocation should produce FAILURE results."""
        coord = MagicMock()

        class FakeResult:
            success = False
            error = "provider error"

        coord.execute = AsyncMock(return_value=FakeResult())
        stage = self._make_stage()
        stage._runtime_coordinator = coord

        steps = [
            ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION, name="s0", item_index=0, order=0
            ),
        ]
        result = await stage.execute(sample_context, steps)
        assert result.outcome == ExecutionOutcome.FAILURE
        assert result.items_failed == 1

    async def test_execute_step_exception(self, sample_context) -> None:
        """Exception during invocation should produce FAILED step result."""
        coord = MagicMock()
        coord.execute = AsyncMock(side_effect=RuntimeError("connection lost"))
        stage = self._make_stage()
        stage._runtime_coordinator = coord

        steps = [
            ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION, name="s0", item_index=0, order=0
            ),
        ]
        result = await stage.execute(sample_context, steps)
        assert result.outcome == ExecutionOutcome.FAILURE
        assert result.items_failed == 1

    async def test_execute_respects_cancellation(self, cancelled_context) -> None:
        """Cancelled context should skip remaining steps."""
        coord = MagicMock()

        class FakeResult:
            success = True
            error = None

        coord.execute = AsyncMock(return_value=FakeResult())
        stage = self._make_stage()
        stage._runtime_coordinator = coord

        steps = [
            ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION, name="s0", item_index=0, order=0
            ),
            ExecutionStep.create(
                stage_type=StageType.PROVIDER_INVOCATION, name="s1", item_index=1, order=1
            ),
        ]
        result = await stage.execute(cancelled_context, steps)
        assert result.items_failed == 0
        assert result.items_succeeded == 0
        skipped = [sr for sr in result.step_results if sr.status == StepStatus.SKIPPED]
        assert len(skipped) == 2

    async def test_rollback_noop(self, sample_context) -> None:
        """Rollback should not raise."""
        stage = self._make_stage()
        fake_result = StageResult(
            stage_type=StageType.PROVIDER_INVOCATION,
            stage_name="test",
            outcome=ExecutionOutcome.SUCCESS,
        )
        await stage.rollback(sample_context, fake_result)


# ---------------------------------------------------------------------------
# Placeholder Stages
# ---------------------------------------------------------------------------


class TestPlaceholderStages:
    """Tests for MetricDispatchStage, AggregationStage, PersistenceStage."""

    async def _run_placeholder(
        self, stage_cls, sample_context, total_steps: int = 2
    ) -> StageResult:
        """Run a placeholder stage with given number of steps."""
        steps = [
            ExecutionStep.create(
                stage_type=stage_cls().stage_type,
                name=f"step_{i}",
                item_index=i,
                order=i,
            )
            for i in range(total_steps)
        ]
        stage = stage_cls()
        return await stage.execute(sample_context, steps)

    async def test_metric_dispatch_success(self, sample_context) -> None:
        """MetricDispatchStage should succeed for all steps."""
        result = await self._run_placeholder(MetricDispatchStage, sample_context)
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 2

    async def test_aggregation_success(self, sample_context) -> None:
        """AggregationStage should succeed for all steps."""
        result = await self._run_placeholder(AggregationStage, sample_context)
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 2

    async def test_persistence_success(self, sample_context) -> None:
        """PersistenceStage should succeed for all steps."""
        result = await self._run_placeholder(PersistenceStage, sample_context)
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 2

    async def test_placeholder_zero_steps(self, sample_context) -> None:
        """Placeholder stage with 0 steps should still succeed."""
        result = await self._run_placeholder(MetricDispatchStage, sample_context, total_steps=0)
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.items_succeeded == 0

    def test_placeholder_stage_type(self) -> None:
        """Each placeholder should have the correct stage type."""
        assert MetricDispatchStage().stage_type == StageType.METRIC_DISPATCH
        assert AggregationStage().stage_type == StageType.AGGREGATION
        assert PersistenceStage().stage_type == StageType.PERSISTENCE

    def test_placeholder_supports_resume(self) -> None:
        """All placeholders should support resume."""
        assert MetricDispatchStage().supports_resume() is True
        assert AggregationStage().supports_resume() is True
        assert PersistenceStage().supports_resume() is True

    def test_placeholder_validate_returns_empty(self, sample_context) -> None:
        """Placeholder validation should return no issues."""
        assert MetricDispatchStage().validate(sample_context) == []
        assert AggregationStage().validate(sample_context) == []
        assert PersistenceStage().validate(sample_context) == []
