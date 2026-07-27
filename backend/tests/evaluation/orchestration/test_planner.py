"""Tests for EvaluationPlanner."""

from __future__ import annotations

import pytest

from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.orchestration.planner import EvaluationPlanner
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.stages.types import StageType

_planner = EvaluationPlanner()


class TestEvaluationPlannerPlan:
    """Tests for EvaluationPlanner.plan()."""

    async def test_plan_creates_dataset_stages(self, sample_run) -> None:
        """Dataset eval should include all four stages."""
        plan = await _planner.plan(sample_run)
        assert StageType.PROVIDER_INVOCATION in plan.stages
        assert StageType.METRIC_DISPATCH in plan.stages
        assert StageType.AGGREGATION in plan.stages
        assert StageType.PERSISTENCE in plan.stages

    async def test_plan_creates_single_stages(self, single_config) -> None:
        """Single eval should only have invocation + metric_dispatch stages."""
        from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

        run = EvaluationRun(
            evaluation_name=single_config.name,
            config=single_config,
            profile=single_config.profile,
        )
        plan = await _planner.plan(run)
        assert plan.stages == (StageType.PROVIDER_INVOCATION, StageType.METRIC_DISPATCH)

    async def test_plan_step_count_matches_dataset(self, sample_run) -> None:
        """Plan should create one step per dataset row."""
        plan = await _planner.plan(sample_run)
        assert len(plan.steps) == sample_run.config.dataset.row_count

    async def test_plan_single_without_dataset(self, single_config) -> None:
        """Single eval without dataset should default to 1 item."""
        from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

        run = EvaluationRun(
            evaluation_name=single_config.name,
            config=single_config,
            profile=single_config.profile,
        )
        plan = await _planner.plan(run)
        assert plan.total_items == 1

    async def test_plan_steps_are_sequential(self, sample_run) -> None:
        """Steps (except first) should depend on previous step."""
        plan = await _planner.plan(sample_run)
        assert len(plan.steps) >= 2
        for idx in range(1, len(plan.steps)):
            step = plan.steps[idx]
            assert step.has_dependencies
            assert len(step.dependencies) == 1

    async def test_plan_first_step_has_no_dependencies(self, sample_run) -> None:
        """First step should have no dependencies."""
        plan = await _planner.plan(sample_run)
        assert not plan.steps[0].has_dependencies

    async def test_plan_metadata(self, sample_run) -> None:
        """Plan should carry correct metadata."""
        plan = await _planner.plan(sample_run)
        assert plan.metadata.created_by == "evaluation_planner"
        assert "Test Evaluation" in plan.metadata.description

    async def test_plan_run_id_matches(self, sample_run) -> None:
        """Plan run_id should match the input run."""
        plan = await _planner.plan(sample_run)
        assert plan.run_id == sample_run.id

    async def test_plan_step_retry_from_policy(self, sample_run) -> None:
        """Steps should use max_retries from policy."""
        plan = await _planner.plan(sample_run)
        for step in plan.steps:
            assert step.max_retries == sample_run.config.policy.max_retries_per_item

    async def test_plan_step_timeout_from_policy(self, sample_run) -> None:
        """Steps should use timeout from policy."""
        plan = await _planner.plan(sample_run)
        for step in plan.steps:
            assert step.timeout_seconds == sample_run.config.policy.timeout_per_item_seconds


class TestEvaluationPlannerValidation:
    """Tests for EvaluationPlanner.validate_plan()."""

    async def test_valid_plan_no_errors(self, sample_run) -> None:
        """Valid plan should return no errors."""
        plan = await _planner.plan(sample_run)
        errors = await _planner.validate_plan(plan)
        assert errors == []

    async def test_plan_no_stages_is_invalid(self, sample_run) -> None:
        """Plan with no stages should fail validation."""
        plan = ExecutionPlan(
            run_id=sample_run.id,
            stages=(),
            steps=(),
            total_items=10,
        )
        errors = await _planner.validate_plan(plan)
        assert any("no stages" in e.lower() for e in errors)

    async def test_plan_negative_items_is_invalid(self, sample_run) -> None:
        """Plan with negative total_items should fail validation."""
        plan = ExecutionPlan(
            run_id=sample_run.id,
            stages=(StageType.PROVIDER_INVOCATION,),
            steps=(),
            total_items=-1,
        )
        errors = await _planner.validate_plan(plan)
        assert any("total_items" in e.lower() for e in errors)

    async def test_plan_items_but_no_steps_is_invalid(self, sample_run) -> None:
        """Plan with items but no steps should fail validation."""
        plan = ExecutionPlan(
            run_id=sample_run.id,
            stages=(StageType.PROVIDER_INVOCATION,),
            steps=(),
            total_items=10,
        )
        errors = await _planner.validate_plan(plan)
        assert any("no steps" in e.lower() for e in errors)

    async def test_plan_zero_items_no_steps_valid(self, sample_run) -> None:
        """Plan with 0 items and no steps should be valid."""
        plan = ExecutionPlan(
            run_id=sample_run.id,
            stages=(StageType.PROVIDER_INVOCATION,),
            steps=(),
            total_items=0,
        )
        errors = await _planner.validate_plan(plan)
        assert errors == []


class TestEvaluationPlannerEstimate:
    """Tests for EvaluationPlanner.estimate()."""

    async def test_estimate_for_dataset(self, sample_run) -> None:
        """Estimate should reflect dataset size and metrics."""
        estimate = await _planner.estimate(sample_run)
        row_count = sample_run.config.dataset.row_count
        metric_count = len(sample_run.config.metrics)
        assert estimate.estimated_steps == row_count
        assert estimate.estimated_tokens > 0
        assert estimate.estimated_cost_usd > 0
        assert estimate.estimated_duration_seconds > 0

    async def test_estimate_for_single(self, single_config) -> None:
        """Estimate for single eval should use 1 item."""
        from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

        run = EvaluationRun(
            evaluation_name=single_config.name,
            config=single_config,
            profile=single_config.profile,
        )
        estimate = await _planner.estimate(run)
        assert estimate.estimated_steps == 1
