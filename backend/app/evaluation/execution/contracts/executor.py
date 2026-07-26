"""Executor contracts for pipeline and stage execution.

These interfaces define the contract between the pipeline
orchestrator and the concrete executors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.step import ExecutionStep
    from app.evaluation.execution.pipeline.pipeline import ExecutionPipeline
    from app.evaluation.execution.results.results import ExecutionResult, StageResult, StepResult


class StageExecutor(ABC):
    """Contract for executing a single pipeline stage.

    Stage executors know how to run the steps of their stage,
    handle retries, and report results.
    """

    @abstractmethod
    async def validate(self, context: PipelineContext) -> list[str]:
        """Validate that the stage can execute.

        Args:
            context: The immutable pipeline context.

        Returns:
            A list of validation errors. Empty means valid.

        """
        ...

    @abstractmethod
    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
    ) -> StageResult:
        """Execute the stage with the given steps.

        Args:
            context: The immutable pipeline context.
            steps: The steps to execute in this stage.

        Returns:
            The result of stage execution.

        """
        ...

    @abstractmethod
    async def rollback(self, context: PipelineContext, result: StageResult) -> None:
        """Roll back any side-effects from a failed stage.

        Args:
            context: The immutable pipeline context.
            result: The (failed) stage result.

        """
        ...

    @abstractmethod
    async def supports_resume(self) -> bool:
        """Return True if the stage can resume from a checkpoint."""
        ...


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
