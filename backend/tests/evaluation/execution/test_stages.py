"""Tests for the stages module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.evaluation.execution.context.context import PipelineContext
from app.evaluation.execution.results.results import StageResult
from app.evaluation.execution.stages.stage import (
    ExecutionStage,
    ValidationIssue,
    ValidationSeverity,
)
from app.evaluation.execution.stages.types import StageType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.pipeline.step import ExecutionStep


class TestStageType:
    """Tests for StageType enum."""

    def test_values(self) -> None:
        """Verify all expected stage types."""
        expected = [
            StageType.PLANNING,
            StageType.PREPARATION,
            StageType.PROVIDER_INVOCATION,
            StageType.METRIC_DISPATCH,
            StageType.AGGREGATION,
            StageType.PERSISTENCE,
            StageType.COMPLETION,
        ]
        assert list(StageType) == expected

    def test_order_unique(self) -> None:
        """Verify each stage has a unique order."""
        orders = [s.order for s in StageType]
        assert len(orders) == len(set(orders))

    def test_order_ascending(self) -> None:
        """Verify stages are in ascending order."""
        for i in range(len(StageType) - 1):
            stage_types = list(StageType)
            assert stage_types[i].order < stage_types[i + 1].order

    def test_description_not_empty(self) -> None:
        """Verify every stage has a description."""
        for stage in StageType:
            assert stage.description
            assert len(stage.description) > 10


class TestExecutionStage:
    """Tests for ExecutionStage abstract base."""

    def test_cannot_instantiate_abstract(self) -> None:
        """Verify ExecutionStage cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ExecutionStage(StageType.PLANNING, "test")  # type: ignore[abstract]

    def test_concrete_stage_creation(self) -> None:
        """Verify a concrete stage can be created."""
        stage = _ConcreteStage(StageType.PLANNING, "TestStage")
        assert stage.stage_type == StageType.PLANNING
        assert stage.name == "TestStage"
        assert stage.order == StageType.PLANNING.order

    def test_stage_type_property(self) -> None:
        """Verify stage_type property."""
        stage = _ConcreteStage(StageType.AGGREGATION, "Aggregation")
        assert stage.stage_type == StageType.AGGREGATION

    def test_name_property(self) -> None:
        """Verify name property."""
        stage = _ConcreteStage(StageType.COMPLETION, "Finalise")
        assert stage.name == "Finalise"

    def test_order_property(self) -> None:
        """Verify order property delegates to stage type."""
        stage = _ConcreteStage(StageType.PROVIDER_INVOCATION, "Invoke")
        assert stage.order == StageType.PROVIDER_INVOCATION.order

    def test_equality(self) -> None:
        """Verify equality based on stage type and name."""
        s1 = _ConcreteStage(StageType.PLANNING, "Plan")
        s2 = _ConcreteStage(StageType.PLANNING, "Plan")
        s3 = _ConcreteStage(StageType.PLANNING, "Other")
        assert s1 == s2
        assert s1 != s3

    def test_hash(self) -> None:
        """Verify hash is consistent."""
        s1 = _ConcreteStage(StageType.PLANNING, "Plan")
        s2 = _ConcreteStage(StageType.PLANNING, "Plan")
        assert hash(s1) == hash(s2)

    def test_repr(self) -> None:
        """Verify repr includes type and name."""
        stage = _ConcreteStage(StageType.PLANNING, "Plan")
        repr_str = repr(stage)
        assert "ConcreteStage" in repr_str
        assert "planning" in repr_str
        assert "Plan" in repr_str

    def test_validate_returns_list(self) -> None:
        """Verify validate returns a list."""
        stage = _ConcreteStage(StageType.PLANNING, "Plan")
        result = stage.validate(PipelineContext())
        assert isinstance(result, list)

    async def test_execute_returns_stage_result(self) -> None:
        """Verify execute returns a StageResult."""
        stage = _ConcreteStage(StageType.PLANNING, "Plan")
        result = await stage.execute(PipelineContext(), [])
        assert isinstance(result, StageResult)

    async def test_rollback(self) -> None:
        """Verify rollback executes without error."""
        stage = _ConcreteStage(StageType.PLANNING, "Plan")
        result = StageResult(stage_type=StageType.PLANNING, stage_name="Plan")
        await stage.rollback(PipelineContext(), result)

    def test_supports_resume(self) -> None:
        """Verify supports_resume returns False by default."""
        stage = _ConcreteStage(StageType.PLANNING, "Plan")
        assert not stage.supports_resume()


class _ConcreteStage(ExecutionStage):
    """Concrete stage for testing."""

    def validate(self, context: PipelineContext) -> list[ValidationIssue]:
        return []

    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
    ) -> StageResult:
        return StageResult(stage_type=self.stage_type, stage_name=self.name)

    async def rollback(self, context: PipelineContext, result: StageResult) -> None:
        pass

    def supports_resume(self) -> bool:
        return False


class TestValidationIssue:
    """Tests for ValidationIssue."""

    def test_default_severity(self) -> None:
        """Verify default severity is ERROR."""
        issue = ValidationIssue("Test error", code="ERR")
        assert issue.severity == ValidationSeverity.ERROR

    def test_custom_severity(self) -> None:
        """Verify custom severity is respected."""
        issue = ValidationIssue("Warning", severity=ValidationSeverity.WARNING)
        assert issue.severity == ValidationSeverity.WARNING

    def test_equality(self) -> None:
        """Verify equality based on message, severity, code."""
        i1 = ValidationIssue("Error", code="E1")
        i2 = ValidationIssue("Error", code="E1")
        i3 = ValidationIssue("Different", code="E1")
        assert i1 == i2
        assert i1 != i3

    def test_hash(self) -> None:
        """Verify hash is consistent."""
        i1 = ValidationIssue("Error", code="E1")
        i2 = ValidationIssue("Error", code="E1")
        assert hash(i1) == hash(i2)

    def test_repr(self) -> None:
        """Verify repr."""
        issue = ValidationIssue("Test error", code="ERR")
        repr_str = repr(issue)
        assert "error" in repr_str
        assert "ERR" in repr_str
        assert "Test error" in repr_str

    def test_details(self) -> None:
        """Verify details dict is preserved."""
        issue = ValidationIssue("Test", code="ERR", details={"key": "value"})
        assert issue.details == {"key": "value"}

    def test_details_default(self) -> None:
        """Verify details defaults to empty dict."""
        issue = ValidationIssue("Test", code="ERR")
        assert issue.details == {}
