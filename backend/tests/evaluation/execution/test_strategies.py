"""Tests for the strategies module."""

from __future__ import annotations

import pytest

from app.evaluation.execution.context.context import ExecutionContext, PipelineContext
from app.evaluation.execution.pipeline.step import ExecutionStep
from app.evaluation.execution.stages.types import StageType
from app.evaluation.execution.strategies.strategies import (
    AdaptiveExecution,
    BudgetAwareExecution,
    ExecutionStrategy,
    ParallelExecution,
    PriorityExecution,
    SequentialExecution,
    StrategyPolicy,
    StrategyType,
)


class TestStrategyType:
    """Tests for StrategyType enum."""

    def test_values(self) -> None:
        """Verify all expected values."""
        expected = {
            StrategyType.SEQUENTIAL,
            StrategyType.PARALLEL,
            StrategyType.ADAPTIVE,
            StrategyType.BUDGET_AWARE,
            StrategyType.PRIORITY,
        }
        assert set(StrategyType) == expected


class TestStrategyPolicy:
    """Tests for StrategyPolicy."""

    def test_defaults(self) -> None:
        """Verify sensible defaults."""
        policy = StrategyPolicy()
        assert policy.strategy_type == StrategyType.SEQUENTIAL
        assert policy.max_concurrency == 1
        assert policy.batch_size == 50

    def test_invalid_concurrency(self) -> None:
        """Verify zero concurrency raises."""
        with pytest.raises(ValueError):
            StrategyPolicy(max_concurrency=0)

    def test_invalid_batch_size(self) -> None:
        """Verify zero batch size raises."""
        with pytest.raises(ValueError):
            StrategyPolicy(batch_size=0)

    def test_negative_retries(self) -> None:
        """Verify negative retries raises."""
        with pytest.raises(ValueError):
            StrategyPolicy(max_retries=-1)

    def test_immutability(self) -> None:
        """Verify StrategyPolicy is frozen."""
        policy = StrategyPolicy()
        with pytest.raises(AttributeError):
            policy.strategy_type = StrategyType.PARALLEL  # type: ignore[misc]


class TestSequentialExecution:
    """Tests for SequentialExecution strategy."""

    @pytest.mark.asyncio
    async def test_strategy_type(self) -> None:
        strategy = SequentialExecution()
        assert strategy.strategy_type == StrategyType.SEQUENTIAL

    @pytest.mark.asyncio
    async def test_order_by_order_field(self) -> None:
        strategy = SequentialExecution()
        s1 = ExecutionStep.create(StageType.PLANNING, "s1", order=2)
        s2 = ExecutionStep.create(StageType.PLANNING, "s2", order=1)
        ordered = await strategy.order([s1, s2], PipelineContext())
        assert list(ordered) == [s2, s1]

    @pytest.mark.asyncio
    async def test_max_concurrency_one(self) -> None:
        strategy = SequentialExecution()
        assert await strategy.max_concurrency(PipelineContext()) == 1


class TestParallelExecution:
    """Tests for ParallelExecution strategy."""

    @pytest.mark.asyncio
    async def test_strategy_type(self) -> None:
        strategy = ParallelExecution()
        assert strategy.strategy_type == StrategyType.PARALLEL

    @pytest.mark.asyncio
    async def test_max_concurrency_from_context(self) -> None:
        strategy = ParallelExecution()
        ctx = PipelineContext(
            execution_context=ExecutionContext(limits=None),
        )
        concurrency = await strategy.max_concurrency(ctx)
        assert concurrency == 4  # Default fallback

    @pytest.mark.asyncio
    async def test_order_by_order_field(self) -> None:
        strategy = ParallelExecution()
        s1 = ExecutionStep.create(StageType.PLANNING, "s1", order=2)
        s2 = ExecutionStep.create(StageType.PLANNING, "s2", order=1)
        ordered = await strategy.order([s1, s2], PipelineContext())
        assert list(ordered) == [s2, s1]


class TestAdaptiveExecution:
    """Tests for AdaptiveExecution strategy."""

    @pytest.mark.asyncio
    async def test_strategy_type(self) -> None:
        strategy = AdaptiveExecution()
        assert strategy.strategy_type == StrategyType.ADAPTIVE

    @pytest.mark.asyncio
    async def test_order_by_priority(self) -> None:
        strategy = AdaptiveExecution()
        s1 = ExecutionStep.create(StageType.PLANNING, "s1", priority=1)
        s2 = ExecutionStep.create(StageType.PLANNING, "s2", priority=5)
        s3 = ExecutionStep.create(StageType.PLANNING, "s3", priority=3)
        ordered = await strategy.order([s1, s2, s3], PipelineContext())
        assert list(ordered) == [s2, s3, s1]


class TestBudgetAwareExecution:
    """Tests for BudgetAwareExecution strategy."""

    @pytest.mark.asyncio
    async def test_strategy_type(self) -> None:
        strategy = BudgetAwareExecution()
        assert strategy.strategy_type == StrategyType.BUDGET_AWARE

    @pytest.mark.asyncio
    async def test_is_execution_strategy(self) -> None:
        strategy = BudgetAwareExecution()
        assert isinstance(strategy, ExecutionStrategy)


class TestPriorityExecution:
    """Tests for PriorityExecution strategy."""

    @pytest.mark.asyncio
    async def test_strategy_type(self) -> None:
        strategy = PriorityExecution()
        assert strategy.strategy_type == StrategyType.PRIORITY

    @pytest.mark.asyncio
    async def test_order_by_priority_reverse(self) -> None:
        strategy = PriorityExecution()
        s1 = ExecutionStep.create(StageType.PLANNING, "s1", priority=1, order=1)
        s2 = ExecutionStep.create(StageType.PLANNING, "s2", priority=5, order=2)
        s3 = ExecutionStep.create(StageType.PLANNING, "s3", priority=3, order=3)
        ordered = await strategy.order([s1, s2, s3], PipelineContext())
        assert list(ordered) == [s2, s3, s1]

    @pytest.mark.asyncio
    async def test_max_concurrency_one(self) -> None:
        strategy = PriorityExecution()
        assert await strategy.max_concurrency(PipelineContext()) == 1

    @pytest.mark.asyncio
    async def test_same_priority_ordered_by_order(self) -> None:
        strategy = PriorityExecution()
        s1 = ExecutionStep.create(StageType.PLANNING, "s1", priority=5, order=10)
        s2 = ExecutionStep.create(StageType.PLANNING, "s2", priority=5, order=1)
        ordered = await strategy.order([s1, s2], PipelineContext())
        # Both same priority, s1 has higher order → comes first with reverse=True
        assert list(ordered) == [s1, s2]
