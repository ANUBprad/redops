"""Tests for the validators module."""

from __future__ import annotations

import pytest

from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.pipeline.step import ExecutionStep, StepDependency
from app.evaluation.execution.stages.types import StageType
from app.evaluation.execution.validators.validators import (
    DependencyGraphValidator,
    PlanValidator,
    StageOrderingValidator,
    ValidationResult,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ValidationError


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_ok(self) -> None:
        """Verify ok factory."""
        result = ValidationResult.ok()
        assert result.valid
        assert result.errors == ()

    def test_failed(self) -> None:
        """Verify failed factory."""
        result = ValidationResult.failed("error1", "error2")
        assert not result.valid
        assert result.errors == ("error1", "error2")


class TestPlanValidator:
    """Tests for PlanValidator."""

    def test_valid_plan(self) -> None:
        """Verify valid plan passes."""
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING],
            steps=[ExecutionStep.create(StageType.PLANNING, "step-1")],
            total_items=10,
        )
        result = PlanValidator.validate(plan)
        assert result.valid

    def test_empty_steps(self) -> None:
        """Verify plan without steps fails."""
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING],
            total_items=10,
        )
        result = PlanValidator.validate(plan)
        assert not result.valid
        assert "at least one step" in result.errors[0]

    def test_empty_stages(self) -> None:
        """Verify plan without stages fails."""
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            steps=[ExecutionStep.create(StageType.PLANNING, "step-1")],
        )
        result = PlanValidator.validate(plan)
        assert not result.valid
        assert "at least one stage" in result.errors[0]

    def test_negative_total_items(self) -> None:
        """Verify negative total_items fails."""
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING],
            steps=[ExecutionStep.create(StageType.PLANNING, "step-1")],
            total_items=-1,
        )
        result = PlanValidator.validate(plan)
        assert not result.valid
        assert "negative" in result.errors[0].lower()

    def test_duplicate_step_ids(self) -> None:
        """Verify duplicate step IDs fail."""
        step_id = UUIDv7.generate()
        step1 = ExecutionStep(
            step_id=step_id,
            stage_type=StageType.PLANNING,
            name="step-1",
        )
        step2 = ExecutionStep(
            step_id=step_id,
            stage_type=StageType.PLANNING,
            name="step-2",
        )
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING],
            steps=[step1, step2],
        )
        result = PlanValidator.validate(plan)
        assert not result.valid
        assert "duplicate" in result.errors[0].lower()

    def test_missing_stage_declaration(self) -> None:
        """Verify steps referencing undeclared stages fail."""
        step = ExecutionStep.create(StageType.PROVIDER_INVOCATION, "inv")
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING],
            steps=[step],
        )
        result = PlanValidator.validate(plan)
        assert not result.valid

    def test_validate_or_raise_ok(self) -> None:
        """Verify validate_or_raise does not raise on valid plan."""
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING],
            steps=[ExecutionStep.create(StageType.PLANNING, "step-1")],
        )
        PlanValidator.validate_or_raise(plan)  # Should not raise

    def test_validate_or_raise_error(self) -> None:
        """Verify validate_or_raise raises on invalid plan."""
        plan = ExecutionPlan.create(
            run_id=UUIDv7.generate(),
            stages=[StageType.PLANNING],
            total_items=10,
        )
        with pytest.raises(ValidationError):
            PlanValidator.validate_or_raise(plan)


class TestDependencyGraphValidator:
    """Tests for DependencyGraphValidator."""

    def test_no_dependencies(self) -> None:
        """Verify steps without deps pass."""
        steps = [
            ExecutionStep.create(StageType.PLANNING, "s1"),
            ExecutionStep.create(StageType.PLANNING, "s2"),
        ]
        result = DependencyGraphValidator.validate(steps)
        assert result.valid

    def test_valid_dependencies(self) -> None:
        """Verify valid dependency chain passes."""
        s1 = ExecutionStep.create(StageType.PLANNING, "s1")
        s2 = ExecutionStep.create(
            StageType.PLANNING,
            "s2",
            dependencies=[StepDependency(step_id=s1.step_id)],
        )
        s3 = ExecutionStep.create(
            StageType.PLANNING,
            "s3",
            dependencies=[StepDependency(step_id=s2.step_id)],
        )
        result = DependencyGraphValidator.validate([s1, s2, s3])
        assert result.valid

    def test_missing_dependency(self) -> None:
        """Verify missing dependency fails."""
        missing_id = UUIDv7.generate()
        s1 = ExecutionStep.create(
            StageType.PLANNING,
            "s1",
            dependencies=[StepDependency(step_id=missing_id)],
        )
        result = DependencyGraphValidator.validate([s1])
        assert not result.valid
        assert "missing" in result.errors[0]

    def test_circular_dependency(self) -> None:
        """Verify circular dependency detection."""
        s1 = ExecutionStep.create(StageType.PLANNING, "s1")
        s2 = ExecutionStep.create(
            StageType.PLANNING,
            "s2",
            dependencies=[StepDependency(step_id=s1.step_id)],
        )
        # Create circular: s1 depends on s2
        s1_circular = ExecutionStep(
            step_id=s1.step_id,
            stage_type=StageType.PLANNING,
            name="s1",
            dependencies=(StepDependency(step_id=s2.step_id),),
        )
        result = DependencyGraphValidator.validate([s1_circular, s2])
        assert not result.valid
        assert "circular" in result.errors[0].lower()

    def test_validate_or_raise_ok(self) -> None:
        """Verify validate_or_raise does not raise on valid deps."""
        steps = [ExecutionStep.create(StageType.PLANNING, "s1")]
        DependencyGraphValidator.validate_or_raise(steps)

    def test_validate_or_raise_error(self) -> None:
        """Verify validate_or_raise raises on invalid deps."""
        missing_id = UUIDv7.generate()
        s1 = ExecutionStep.create(
            StageType.PLANNING,
            "s1",
            dependencies=[StepDependency(step_id=missing_id)],
        )
        with pytest.raises(ValidationError):
            DependencyGraphValidator.validate_or_raise([s1])


class TestStageOrderingValidator:
    """Tests for StageOrderingValidator."""

    def test_valid_ordering(self) -> None:
        """Verify correct canonical order passes."""
        stages = [
            StageType.PLANNING,
            StageType.PREPARATION,
            StageType.PROVIDER_INVOCATION,
        ]
        result = StageOrderingValidator.validate(stages)
        assert result.valid

    def test_invalid_ordering(self) -> None:
        """Verify out-of-order stages fail."""
        stages = [
            StageType.PROVIDER_INVOCATION,
            StageType.PLANNING,
        ]
        result = StageOrderingValidator.validate(stages)
        assert not result.valid
        assert "must come before" in result.errors[0]

    def test_empty_stages(self) -> None:
        """Verify empty stages fail."""
        result = StageOrderingValidator.validate([])
        assert not result.valid

    def test_duplicate_stages(self) -> None:
        """Verify duplicate stages fail."""
        stages = [StageType.PLANNING, StageType.PLANNING]
        result = StageOrderingValidator.validate(stages)
        assert not result.valid
        assert "duplicate" in result.errors[0].lower()

    def test_single_stage(self) -> None:
        """Verify single stage is always valid."""
        result = StageOrderingValidator.validate([StageType.PLANNING])
        assert result.valid
