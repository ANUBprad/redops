"""Tests for the results module."""

from __future__ import annotations

from app.evaluation.execution.pipeline.step import StepStatus
from app.evaluation.execution.results.results import (
    ExecutionOutcome,
    ExecutionResult,
    ExecutionStatistics,
    FailureReport,
    PipelineSummary,
    StageResult,
    StepResult,
)
from app.evaluation.execution.stages.stage import StageType
from app.kernel.entities.base import UUIDv7


class TestExecutionOutcome:
    """Tests for ExecutionOutcome enum."""

    def test_values(self) -> None:
        """Verify all expected values."""
        assert ExecutionOutcome.SUCCESS.value == "success"
        assert ExecutionOutcome.FAILURE.value == "failure"
        assert ExecutionOutcome.SKIPPED.value == "skipped"
        assert ExecutionOutcome.CANCELLED.value == "cancelled"
        assert ExecutionOutcome.TIMEOUT.value == "timeout"


class TestStepResult:
    """Tests for StepResult."""

    def test_creation(self) -> None:
        """Verify basic result creation."""
        step_id = UUIDv7.generate()
        result = StepResult(
            step_id=step_id,
            step_name="test-step",
            stage_type=StageType.PLANNING,
            status=StepStatus.COMPLETED,
        )
        assert result.step_id == step_id
        assert result.step_name == "test-step"
        assert result.stage_type == StageType.PLANNING
        assert result.status == StepStatus.COMPLETED
        assert result.is_success
        assert not result.is_failure

    def test_failure_result(self) -> None:
        """Verify failure result properties."""
        result = StepResult(
            step_id=UUIDv7.generate(),
            step_name="fail-step",
            stage_type=StageType.PLANNING,
            status=StepStatus.FAILED,
            outcome=ExecutionOutcome.FAILURE,
            error="Something went wrong",
        )
        assert not result.is_success
        assert result.is_failure
        assert result.error == "Something went wrong"

    def test_defaults(self) -> None:
        """Verify sensible defaults."""
        result = StepResult(
            step_id=UUIDv7.generate(),
            step_name="s1",
            stage_type=StageType.PLANNING,
            status=StepStatus.PENDING,
        )
        assert result.outcome == ExecutionOutcome.SUCCESS
        assert result.duration_ms == 0
        assert result.error is None
        assert result.retry_count == 0
        assert result.metadata == {}


class TestStageResult:
    """Tests for StageResult."""

    def test_creation(self) -> None:
        """Verify basic stage result creation."""
        result = StageResult(
            stage_type=StageType.PLANNING,
            stage_name="Planning Stage",
        )
        assert result.stage_type == StageType.PLANNING
        assert result.stage_name == "Planning Stage"
        assert result.is_success
        assert result.total_steps == 0

    def test_with_step_results(self) -> None:
        """Verify stage result with step results."""
        step_result = StepResult(
            step_id=UUIDv7.generate(),
            step_name="s1",
            stage_type=StageType.PLANNING,
            status=StepStatus.COMPLETED,
        )
        result = StageResult(
            stage_type=StageType.PLANNING,
            stage_name="Planning",
            step_results=(step_result,),
        )
        assert result.total_steps == 1
        assert len(result.successful_steps) == 1
        assert len(result.failed_steps) == 0

    def test_failed_steps(self) -> None:
        """Verify failed steps are separated."""
        failed_step = StepResult(
            step_id=UUIDv7.generate(),
            step_name="f1",
            stage_type=StageType.PLANNING,
            status=StepStatus.FAILED,
            outcome=ExecutionOutcome.FAILURE,
        )
        success_step = StepResult(
            step_id=UUIDv7.generate(),
            step_name="s1",
            stage_type=StageType.PLANNING,
            status=StepStatus.COMPLETED,
        )
        result = StageResult(
            stage_type=StageType.PLANNING,
            stage_name="Test",
            step_results=(failed_step, success_step),
        )
        assert len(result.successful_steps) == 1
        assert len(result.failed_steps) == 1


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_creation(self) -> None:
        """Verify basic execution result creation."""
        result = ExecutionResult(run_id=UUIDv7.generate())
        assert result.is_success
        assert result.total_stages == 0
        assert result.total_items == 0

    def test_with_stage_results(self) -> None:
        """Verify execution result with stage results."""
        stage_result = StageResult(
            stage_type=StageType.PLANNING,
            stage_name="Plan",
        )
        result = ExecutionResult(
            run_id=UUIDv7.generate(),
            stage_results=(stage_result,),
        )
        assert result.total_stages == 1
        assert len(result.successful_stages) == 1


class TestFailureReport:
    """Tests for FailureReport."""

    def test_defaults(self) -> None:
        """Verify default failure report."""
        report = FailureReport()
        assert not report.has_failures
        assert report.total_failures == 0

    def test_with_failures(self) -> None:
        """Verify failure report with failures."""
        step_result = StepResult(
            step_id=UUIDv7.generate(),
            step_name="f1",
            stage_type=StageType.PLANNING,
            status=StepStatus.FAILED,
            outcome=ExecutionOutcome.FAILURE,
            error="Error 1",
        )
        report = FailureReport(
            total_failures=1,
            step_failures=(step_result,),
            first_failure_message="Error 1",
            last_failure_message="Error 1",
        )
        assert report.has_failures
        assert report.total_failures == 1
        assert report.first_failure_message == "Error 1"


class TestExecutionStatistics:
    """Tests for ExecutionStatistics."""

    def test_defaults(self) -> None:
        """Verify default statistics."""
        stats = ExecutionStatistics()
        assert stats.total_steps == 0
        assert stats.success_rate == 1.0

    def test_success_rate(self) -> None:
        """Verify success rate calculation."""
        stats = ExecutionStatistics(total_steps=10, completed_steps=7)
        assert stats.success_rate == 0.7

    def test_zero_steps(self) -> None:
        """Verify success rate with zero steps."""
        stats = ExecutionStatistics()
        assert stats.success_rate == 1.0


class TestPipelineSummary:
    """Tests for PipelineSummary."""

    def test_creation(self) -> None:
        """Verify basic summary creation."""
        summary = PipelineSummary(run_id=UUIDv7.generate())
        assert summary.is_success
        assert summary.outcome == ExecutionOutcome.SUCCESS

    def test_from_execution_result(self) -> None:
        """Verify summary creation from execution result."""
        result = ExecutionResult(
            run_id=UUIDv7.generate(),
            outcome=ExecutionOutcome.SUCCESS,
            total_duration_ms=1000,
            items_processed=50,
            items_succeeded=45,
            items_failed=5,
        )
        summary = PipelineSummary.from_execution_result(result, plan_version=2)
        assert summary.run_id == result.run_id
        assert summary.outcome == ExecutionOutcome.SUCCESS
        assert summary.plan_version == 2
        assert summary.items_processed == 50
        assert summary.items_succeeded == 45
        assert summary.items_failed == 5

    def test_from_failed_result(self) -> None:
        """Verify summary from failed result."""
        result = ExecutionResult(
            run_id=UUIDv7.generate(),
            outcome=ExecutionOutcome.FAILURE,
        )
        summary = PipelineSummary.from_execution_result(result)
        assert not summary.is_success
        assert summary.outcome == ExecutionOutcome.FAILURE
