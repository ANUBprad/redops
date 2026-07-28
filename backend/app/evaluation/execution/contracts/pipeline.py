"""Pipeline contract — the top-level execution interface.

Defines the lifecycle of a pipeline: run, pause, resume, cancel.
No implementations here — only abstract contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.results.results import ExecutionResult, PipelineSummary


class Pipeline(ABC):
    """Contract for an executable pipeline.

    A pipeline is the top-level execution container. It takes a
    PipelineContext, executes stages in order, and produces an
    ExecutionResult.
    """

    @abstractmethod
    async def run(self, context: PipelineContext) -> ExecutionResult:
        """Execute the pipeline with the given context.

        Args:
            context: The immutable pipeline context.

        Returns:
            The result of pipeline execution.

        """
        ...

    @abstractmethod
    async def pause(self) -> None:
        """Request a graceful pause after the current stage completes."""
        ...

    @abstractmethod
    async def resume(self, context: PipelineContext) -> ExecutionResult:
        """Resume execution from the last checkpoint.

        Args:
            context: The updated pipeline context.

        Returns:
            The result of resumed pipeline execution.

        """
        ...

    @abstractmethod
    async def cancel(self, *, force: bool = False) -> None:
        """Request cancellation of pipeline execution.

        Args:
            force: If True, abandon in-flight work immediately.

        """
        ...

    @abstractmethod
    async def summary(self) -> PipelineSummary:
        """Return a summary of the current execution state.

        Returns:
            A PipelineSummary suitable for API responses.

        """
        ...
