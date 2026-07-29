"""Tests for the plan module."""

from __future__ import annotations

import pytest

from app.evaluation.execution.pipeline.plan import ExecutionPlan, PlanMetadata
from app.evaluation.execution.pipeline.step import ExecutionStep
from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7


class TestPlanMetadata:
    """Tests for PlanMetadata."""

    def test_defaults(self) -> None:
        """Verify default metadata values."""
        meta = PlanMetadata()
        assert meta.created_by == "system"
        assert meta.description == ""
        assert meta.tags == ()


class TestExecutionPlan:
    """Tests for ExecutionPlan."""

    def test_creation(self) -> None:
        """Verify basic plan creation."""
        run_id = UUIDv7.generate()
        plan = ExecutionPlan.create(run_id=run_id)
        assert plan.run_id == run_id
        assert plan.plan_id is not None
        assert plan.version == 1
        assert plan.stages == ()
        assert plan.steps == ()
        assert plan.total_items == 0
        assert plan.step_count == 0
        assert plan.stage_count == 0

    def test_create_with_stages_and_steps(self) -> None:
        """Verify plan creation with stages and steps."""
        run_id = UUIDv7.generate()
        stages = [StageType.PLANNING, StageType.PREPARATION]
        steps = [
            ExecutionStep.create(StageType.PLANNING, "plan-step"),
            ExecutionStep.create(StageType.PREPARATION, "prep-step"),
        ]
        plan = ExecutionPlan.create(
            run_id=run_id,
            stages=stages,
            steps=steps,
            total_items=100,
        )
        assert plan.run_id == run_id
        assert plan.stages == (StageType.PLANNING, StageType.PREPARATION)
        assert len(plan.steps) == 2
        assert plan.total_items == 100
        assert plan.step_count == 2
        assert plan.stage_count == 2

    def test_stage_types_sorted(self) -> None:
        """Verify stage_types returns stages sorted by order."""
        stages = [StageType.PROVIDER_INVOCATION, StageType.PLANNING]
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=stages,
        )
        sorted_types = plan.stage_types
        assert sorted_types == [StageType.PLANNING, StageType.PROVIDER_INVOCATION]

    def test_steps_by_stage(self) -> None:
        """Verify steps are grouped by stage type."""
        steps = [
            ExecutionStep.create(StageType.PLANNING, "p1"),
            ExecutionStep.create(StageType.PLANNING, "p2"),
            ExecutionStep.create(StageType.PREPARATION, "prep1"),
        ]
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING, StageType.PREPARATION],
            steps=steps,
        )
        grouped = plan.steps_by_stage
        assert len(grouped[StageType.PLANNING]) == 2
        assert len(grouped[StageType.PREPARATION]) == 1

    def test_steps_for_stage(self) -> None:
        """Verify steps_for_stage returns correct steps."""
        steps = [
            ExecutionStep.create(StageType.PLANNING, "p1"),
            ExecutionStep.create(StageType.PROVIDER_INVOCATION, "inv1"),
        ]
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            steps=steps,
        )
        planning_steps = plan.steps_for_stage(StageType.PLANNING)
        assert len(planning_steps) == 1
        assert planning_steps[0].name == "p1"

    def test_versioning(self) -> None:
        """Verify with_version creates new plan with updated version."""
        plan = ExecutionPlan.create(run_id=UUIDv7.generate(), version=1)
        plan_v2 = plan.with_version(2)
        assert plan_v2.version == 2
        assert plan.version == 1  # Original unchanged
        assert plan_v2.plan_id == plan.plan_id
        assert plan_v2.run_id == plan.run_id

    def test_increment_version(self) -> None:
        """Verify increment_version."""
        plan = ExecutionPlan.create(run_id=UUIDv7.generate(), version=1)
        plan_v2 = plan.increment_version()
        assert plan_v2.version == 2

    def test_immutability(self) -> None:
        """Verify ExecutionPlan is frozen."""
        plan = ExecutionPlan.create(run_id=UUIDv7.generate())
        with pytest.raises(AttributeError):
            plan.version = 5  # type: ignore[misc]

    def test_steps_immutable_tuple(self) -> None:
        """Verify steps are stored as immutable tuple."""
        steps = [ExecutionStep.create(StageType.PLANNING, "s1")]
        plan = ExecutionPlan.create(run_id=UUIDv7.generate(), steps=steps)
        assert isinstance(plan.steps, tuple)

    def test_custom_metadata(self) -> None:
        """Verify custom metadata is preserved."""
        meta = PlanMetadata(
            created_by="user-1",
            description="Test plan",
            tags=("test", "demo"),
        )
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            metadata=meta,
        )
        assert plan.metadata.created_by == "user-1"
        assert plan.metadata.description == "Test plan"
        assert plan.metadata.tags == ("test", "demo")
