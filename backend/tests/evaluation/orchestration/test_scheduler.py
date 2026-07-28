"""Tests for SequentialScheduler and ParallelScheduler."""

from __future__ import annotations

import pytest

from app.evaluation.orchestration.scheduler import ParallelScheduler, SequentialScheduler
from app.evaluation.execution.pipeline.step import ExecutionStep, StepDependency
from app.evaluation.execution.stages.types import StageType


def _make_step(order: int, name: str = "", deps=None) -> ExecutionStep:
    """Build an ExecutionStep."""
    return ExecutionStep.create(
        stage_type=StageType.PROVIDER_INVOCATION,
        name=name or f"step_{order}",
        item_index=order,
        order=order,
        dependencies=deps or [],
    )


class TestSequentialScheduler:
    """Tests for SequentialScheduler."""

    async def test_returns_steps_in_order(self, sample_context) -> None:
        """Steps should be returned sorted by order attribute."""
        scheduler = SequentialScheduler()
        s2 = _make_step(2)
        s0 = _make_step(0)
        s1 = _make_step(1)
        result = await scheduler.schedule([s2, s0, s1], sample_context)
        assert [s.order for s in result] == [0, 1, 2]

    async def test_empty_steps(self, sample_context) -> None:
        """Empty input should return empty output."""
        scheduler = SequentialScheduler()
        result = await scheduler.schedule([], sample_context)
        assert result == []

    async def test_single_step(self, sample_context) -> None:
        """Single step should be returned as-is."""
        scheduler = SequentialScheduler()
        step = _make_step(0)
        result = await scheduler.schedule([step], sample_context)
        assert len(result) == 1


class TestParallelScheduler:
    """Tests for ParallelScheduler."""

    async def test_independent_steps_come_first(self, sample_context) -> None:
        """Steps without dependencies should appear before dependent steps."""
        scheduler = ParallelScheduler()
        dep_id = _make_step(0).step_id
        dependent = _make_step(2, deps=[StepDependency(step_id=dep_id)])
        independent = _make_step(1)
        result = await scheduler.schedule([dependent, independent], sample_context)
        assert result[0].step_id == independent.step_id
        assert result[1].step_id == dependent.step_id

    async def test_independent_sorted_by_order(self, sample_context) -> None:
        """Independent steps should be sorted by order."""
        scheduler = ParallelScheduler()
        s2 = _make_step(2)
        s0 = _make_step(0)
        result = await scheduler.schedule([s2, s0], sample_context)
        assert result[0].order == 0
        assert result[1].order == 2

    async def test_dependent_sorted_by_depth(self, sample_context) -> None:
        """Dependent steps should be sorted by dependency depth then order."""
        scheduler = ParallelScheduler()
        dep_id = _make_step(0).step_id
        deep = _make_step(3, deps=[StepDependency(step_id=dep_id)])
        shallow = _make_step(2, deps=[StepDependency(step_id=dep_id)])
        result = await scheduler.schedule([deep, shallow], sample_context)
        assert result[0].order == 2
        assert result[1].order == 3

    async def test_empty_input(self, sample_context) -> None:
        """Empty input should return empty output."""
        scheduler = ParallelScheduler()
        result = await scheduler.schedule([], sample_context)
        assert result == []

    async def test_all_independent(self, sample_context) -> None:
        """All independent steps should be sorted by order."""
        scheduler = ParallelScheduler()
        s2 = _make_step(2)
        s0 = _make_step(0)
        s1 = _make_step(1)
        result = await scheduler.schedule([s2, s0, s1], sample_context)
        assert [s.order for s in result] == [0, 1, 2]

    async def test_mixed_dependencies(self, sample_context) -> None:
        """Mix of independent and dependent steps should be correctly ordered."""
        scheduler = ParallelScheduler()
        dep_id = _make_step(0).step_id
        independent = _make_step(5)
        dependent = _make_step(3, deps=[StepDependency(step_id=dep_id)])
        result = await scheduler.schedule([dependent, independent], sample_context)
        assert result[0].step_id == independent.step_id
        assert result[1].step_id == dependent.step_id
