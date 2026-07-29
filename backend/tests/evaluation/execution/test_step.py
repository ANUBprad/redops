"""Tests for the step module."""

from __future__ import annotations

import pytest

from app.evaluation.execution.pipeline.step import (
    DependencyType,
    ExecutionStep,
    StepDependency,
    StepStatus,
)
from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_terminal_states(self) -> None:
        """Verify terminal states."""
        assert StepStatus.COMPLETED.is_terminal
        assert StepStatus.FAILED.is_terminal
        assert StepStatus.SKIPPED.is_terminal

    def test_non_terminal_states(self) -> None:
        """Verify non-terminal states."""
        assert not StepStatus.PENDING.is_terminal
        assert not StepStatus.RUNNING.is_terminal


class TestStepDependency:
    """Tests for StepDependency data class."""

    def test_creation(self) -> None:
        """Verify creation with default type."""
        dep_id = UUIDv7.generate()
        dep = StepDependency(step_id=dep_id)
        assert dep.step_id == dep_id
        assert dep.dependency_type == DependencyType.HARD

    def test_soft_dependency(self) -> None:
        """Verify soft dependency type."""
        dep_id = UUIDv7.generate()
        dep = StepDependency(step_id=dep_id, dependency_type=DependencyType.SOFT)
        assert dep.dependency_type == DependencyType.SOFT

    def test_immutability(self) -> None:
        """Verify StepDependency is frozen."""
        dep = StepDependency(step_id=UUIDv7.generate())
        with pytest.raises(AttributeError):
            dep.step_id = UUIDv7.generate()  # type: ignore[misc]

    def test_hash_and_eq(self) -> None:
        """Verify equality and hash."""
        dep_id = UUIDv7.generate()
        d1 = StepDependency(step_id=dep_id)
        d2 = StepDependency(step_id=dep_id)
        assert d1 == d2
        assert hash(d1) == hash(d2)


class TestExecutionStep:
    """Tests for ExecutionStep data class."""

    def test_creation(self) -> None:
        """Verify basic step creation."""
        step = ExecutionStep(
            stage_type=StageType.PROVIDER_INVOCATION,
            name="invoke-gpt4",
        )
        assert step.stage_type == StageType.PROVIDER_INVOCATION
        assert step.name == "invoke-gpt4"
        assert step.step_id is not None

    def test_create_factory(self) -> None:
        """Verify factory method creates valid steps."""
        step = ExecutionStep.create(
            stage_type=StageType.METRIC_DISPATCH,
            name="compute-accuracy",
            item_index=5,
            max_retries=2,
            timeout_seconds=30,
            priority=1,
            order=10,
            metadata={"model": "gpt-4"},
        )
        assert step.stage_type == StageType.METRIC_DISPATCH
        assert step.name == "compute-accuracy"
        assert step.item_index == 5
        assert step.max_retries == 2
        assert step.timeout_seconds == 30
        assert step.priority == 1
        assert step.order == 10
        assert step.metadata == {"model": "gpt-4"}

    def test_default_values(self) -> None:
        """Verify sensible defaults."""
        step = ExecutionStep.create(StageType.PLANNING, "plan")
        assert step.max_retries == 0
        assert step.timeout_seconds is None
        assert step.priority == 0
        assert step.order == 0
        assert step.item_index is None
        assert step.dependencies == ()
        assert step.metadata == {}

    def test_has_dependencies_true(self) -> None:
        """Verify has_dependencies with dependencies."""
        dep = StepDependency(step_id=UUIDv7.generate())
        step = ExecutionStep.create(
            StageType.PLANNING,
            "plan",
            dependencies=[dep],
        )
        assert step.has_dependencies

    def test_has_dependencies_false(self) -> None:
        """Verify has_dependencies without dependencies."""
        step = ExecutionStep.create(StageType.PLANNING, "plan")
        assert not step.has_dependencies

    def test_hard_dependency_ids(self) -> None:
        """Verify hard dependency extraction."""
        id1 = UUIDv7.generate()
        id2 = UUIDv7.generate()
        dep1 = StepDependency(step_id=id1, dependency_type=DependencyType.HARD)
        dep2 = StepDependency(step_id=id2, dependency_type=DependencyType.SOFT)
        step = ExecutionStep.create(
            StageType.PLANNING,
            "plan",
            dependencies=[dep1, dep2],
        )
        assert id1 in step.hard_dependency_ids
        assert id2 not in step.hard_dependency_ids

    def test_soft_dependency_ids(self) -> None:
        """Verify soft dependency extraction."""
        id1 = UUIDv7.generate()
        id2 = UUIDv7.generate()
        dep1 = StepDependency(step_id=id1, dependency_type=DependencyType.HARD)
        dep2 = StepDependency(step_id=id2, dependency_type=DependencyType.SOFT)
        step = ExecutionStep.create(
            StageType.PLANNING,
            "plan",
            dependencies=[dep1, dep2],
        )
        assert id2 in step.soft_dependency_ids
        assert id1 not in step.soft_dependency_ids

    def test_all_dependency_ids(self) -> None:
        """Verify all dependency IDs."""
        id1 = UUIDv7.generate()
        id2 = UUIDv7.generate()
        dep1 = StepDependency(step_id=id1)
        dep2 = StepDependency(step_id=id2)
        step = ExecutionStep.create(
            StageType.PLANNING,
            "plan",
            dependencies=[dep1, dep2],
        )
        assert id1 in step.all_dependency_ids
        assert id2 in step.all_dependency_ids

    def test_requires_retry_true(self) -> None:
        """Verify requires_retry with max_retries > 0."""
        step = ExecutionStep.create(StageType.PLANNING, "plan", max_retries=3)
        assert step.requires_retry

    def test_requires_retry_false(self) -> None:
        """Verify requires_retry with max_retries == 0."""
        step = ExecutionStep.create(StageType.PLANNING, "plan")
        assert not step.requires_retry

    def test_immutability(self) -> None:
        """Verify ExecutionStep is frozen."""
        step = ExecutionStep.create(StageType.PLANNING, "plan")
        with pytest.raises(AttributeError):
            step.name = "changed"  # type: ignore[misc]

    def test_unique_step_ids(self) -> None:
        """Verify each factory call generates a unique ID."""
        steps = [ExecutionStep.create(StageType.PLANNING, f"step-{i}") for i in range(10)]
        ids = {s.step_id for s in steps}
        assert len(ids) == 10
