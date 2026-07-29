"""Concrete ExecutionScheduler implementations.

Provides sequential and parallel scheduling strategies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.execution.contracts.scheduler import ExecutionScheduler

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.step import ExecutionStep


class SequentialScheduler(ExecutionScheduler):
    """Returns steps in deterministic order (default).

    Steps are sorted by their order attribute. No concurrency —
    steps execute one at a time.
    """

    async def schedule(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,
    ) -> Sequence[ExecutionStep]:
        """Return steps sorted by order for sequential execution."""
        return sorted(steps, key=lambda s: (s.order, s.step_id))


class ParallelScheduler(ExecutionScheduler):
    """Groups steps by independence for concurrent execution.

    Steps with no dependencies are grouped together for parallel
    execution. Steps with dependencies are sequenced after their
    prerequisites.
    """

    async def schedule(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,
    ) -> Sequence[ExecutionStep]:
        """Return steps in parallel-compatible order.

        Independent steps (no dependencies) come first, followed
        by dependent steps sorted by dependency depth.
        """
        independent = [s for s in steps if not s.has_dependencies]
        dependent = [s for s in steps if s.has_dependencies]

        independent_sorted = sorted(independent, key=lambda s: s.order)
        dependent_sorted = sorted(
            dependent,
            key=lambda s: (len(s.dependencies), s.order),
        )

        return list(independent_sorted) + list(dependent_sorted)
