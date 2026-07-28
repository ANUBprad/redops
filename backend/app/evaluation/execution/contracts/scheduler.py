"""ExecutionScheduler contract — interface only.

The scheduler is responsible for deciding when and in what order
steps are dispatched to executors. No implementation is provided
in this layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.step import ExecutionStep


class ExecutionScheduler(ABC):
    """Contract for scheduling step execution.

    Implementations use the chosen execution strategy to determine
    the order and concurrency of step dispatch.
    """

    @abstractmethod
    async def schedule(
        self,
        steps: Sequence[ExecutionStep],
        context: PipelineContext,
    ) -> Sequence[ExecutionStep]:
        """Return steps in the order they should be executed.

        Args:
            steps: The steps to schedule.
            context: The pipeline context (includes strategy info).

        Returns:
            An ordered sequence of steps to execute.

        """
        ...
