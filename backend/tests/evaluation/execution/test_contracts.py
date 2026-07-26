"""Tests for the contracts module."""

from __future__ import annotations

from app.evaluation.execution.contracts.executor import PipelineExecutor, StageExecutor
from app.evaluation.execution.contracts.observer import ExecutionObserver
from app.evaluation.execution.contracts.pipeline import Pipeline
from app.evaluation.execution.contracts.planner import ExecutionPlanner, PlanEstimate
from app.evaluation.execution.contracts.scheduler import ExecutionScheduler


class TestContractInterfaces:
    """Verify all contract interfaces are abstract and importable."""

    def test_pipeline_is_abstract(self) -> None:
        """Verify Pipeline cannot be instantiated."""
        try:
            Pipeline()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_pipeline_executor_is_abstract(self) -> None:
        """Verify PipelineExecutor cannot be instantiated."""
        try:
            PipelineExecutor()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_stage_executor_is_abstract(self) -> None:
        """Verify StageExecutor cannot be instantiated."""
        try:
            StageExecutor()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_execution_planner_is_abstract(self) -> None:
        """Verify ExecutionPlanner cannot be instantiated."""
        try:
            ExecutionPlanner()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_execution_scheduler_is_abstract(self) -> None:
        """Verify ExecutionScheduler cannot be instantiated."""
        try:
            ExecutionScheduler()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_execution_observer_is_abstract(self) -> None:
        """Verify ExecutionObserver cannot be instantiated."""
        try:
            ExecutionObserver()  # type: ignore[abstract]
            assert False, "Should have raised TypeError"
        except TypeError:
            pass


class TestPlanEstimate:
    """Tests for PlanEstimate."""

    def test_creation(self) -> None:
        """Verify estimate creation with defaults."""
        estimate = PlanEstimate()
        assert estimate.estimated_steps == 0
        assert estimate.estimated_duration_seconds == 0
        assert estimate.estimated_cost_usd == 0.0
        assert estimate.estimated_tokens == 0

    def test_custom_values(self) -> None:
        """Verify custom estimate values."""
        estimate = PlanEstimate(
            estimated_steps=100,
            estimated_duration_seconds=3600,
            estimated_cost_usd=0.50,
            estimated_tokens=50000,
        )
        assert estimate.estimated_steps == 100
        assert estimate.estimated_duration_seconds == 3600
        assert estimate.estimated_cost_usd == 0.50
        assert estimate.estimated_tokens == 50000

    def test_repr(self) -> None:
        """Verify repr contains relevant info."""
        estimate = PlanEstimate(
            estimated_steps=50,
            estimated_duration_seconds=120,
            estimated_cost_usd=0.25,
        )
        repr_str = repr(estimate)
        assert "50" in repr_str
        assert "120" in repr_str
        assert "0.25" in repr_str
