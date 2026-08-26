"""Executor contracts for pipeline and stage execution.

These interfaces define the contract between the pipeline
orchestrator and the concrete executors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
    from app.evaluation.execution.results.results import ExecutionResult


class PipelineExecutor(ABC):
    """Contract for executing an entire pipeline.

    The pipeline executor orchestrates stage execution in order,
    handling pause, resume, cancellation, and error propagation.
    """

    @abstractmethod
    async def execute(
        self,
        pipeline: ExecutionPipeline,
        context: PipelineContext,
    ) -> ExecutionResult:
        """Execute the full pipeline.

        Args:
            pipeline: The pipeline to execute.
            context: The immutable pipeline context.

        Returns:
            The overall execution result.

        """
        ...
