"""Execution strategy interfaces and policy objects.

Strategies determine how steps and stages are scheduled and
executed — sequentially, in parallel, adaptively, or under
budget/priority constraints.

Only interfaces and policy objects are defined here.
No concrete execution logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.step import ExecutionStep


@unique
class StrategyType(Enum):
    """Type of execution strategy."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"
    BUDGET_AWARE = "budget_aware"
    PRIORITY = "priority"


class ExecutionStrategy(ABC):
    """Abstract base for an execution strategy.

    A strategy decides the order and concurrency of step execution.
    """

    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        """Return the type of this strategy."""
        ...

    @abstractmethod
    async def order(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,
    ) -> Sequence[ExecutionStep]:
        """Return steps in the order they should be executed.

        Args:
            steps: Available steps to order.
            context: Pipeline context for strategy decisions.

        Returns:
            Steps in execution order.

        """
        ...

    @abstractmethod
    async def max_concurrency(self, context: PipelineContext) -> int:
        """Return the maximum concurrency level for this strategy.

        Args:
            context: Pipeline context for resource decisions.

        Returns:
            Maximum number of concurrent step executions.

        """
        ...


@dataclass(frozen=True, slots=True)
class StrategyPolicy:
    """Policy configuration for an execution strategy.

    This is a pure policy object — no execution logic.
    """

    strategy_type: StrategyType = StrategyType.SEQUENTIAL
    max_concurrency: int = 1
    batch_size: int = 50
    timeout_seconds_per_step: int | None = None
    retry_on_failure: bool = True
    max_retries: int = 0

    def __post_init__(self) -> None:
        """Validate policy invariants."""
        if self.max_concurrency < 1:
            msg = "max_concurrency must be >= 1"
            raise ValueError(msg)
        if self.batch_size < 1:
            msg = "batch_size must be >= 1"
            raise ValueError(msg)
        if self.max_retries < 0:
            msg = "max_retries cannot be negative"
            raise ValueError(msg)


class SequentialExecution(ExecutionStrategy):
    """Strategy interface for sequential execution.

    Steps are executed one after another, in order.
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.SEQUENTIAL

    async def order(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,  # noqa: ARG002
    ) -> Sequence[ExecutionStep]:
        return sorted(steps, key=lambda s: s.order)

    async def max_concurrency(
        self,
        context: PipelineContext,  # noqa: ARG002
    ) -> int:
        return 1


class ParallelExecution(ExecutionStrategy):
    """Strategy interface for parallel execution.

    Steps can be executed concurrently, respecting dependencies
    and the configured concurrency limit.
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.PARALLEL

    async def order(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,  # noqa: ARG002
    ) -> Sequence[ExecutionStep]:
        return sorted(steps, key=lambda s: s.order)

    async def max_concurrency(self, context: PipelineContext) -> int:
        if context.execution_context.limits is not None:
            return context.execution_context.limits.max_concurrency
        return 4


class AdaptiveExecution(ExecutionStrategy):
    """Strategy interface for adaptive execution.

    The strategy dynamically adjusts concurrency based on
    observed performance and resource availability.
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.ADAPTIVE

    async def order(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,  # noqa: ARG002
    ) -> Sequence[ExecutionStep]:
        return sorted(steps, key=lambda s: s.priority, reverse=True)

    async def max_concurrency(self, context: PipelineContext) -> int:
        return await ParallelExecution().max_concurrency(context)


class BudgetAwareExecution(ExecutionStrategy):
    """Strategy interface for budget-aware execution.

    The strategy monitors budget consumption and may reduce
    concurrency or skip steps when budgets are near limits.
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.BUDGET_AWARE

    async def order(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,  # noqa: ARG002
    ) -> Sequence[ExecutionStep]:
        # Budget-aware ordering prefers lower-cost steps first
        return sorted(steps, key=lambda s: s.priority, reverse=True)

    async def max_concurrency(self, context: PipelineContext) -> int:
        return await ParallelExecution().max_concurrency(context)


class PriorityExecution(ExecutionStrategy):
    """Strategy interface for priority-based execution.

    Higher-priority steps are executed before lower-priority ones.
    """

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.PRIORITY

    async def order(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,  # noqa: ARG002
    ) -> Sequence[ExecutionStep]:
        return sorted(steps, key=lambda s: (s.priority, s.order), reverse=True)

    async def max_concurrency(
        self,
        context: PipelineContext,  # noqa: ARG002
    ) -> int:
        return 1
