"""ExecutionObserver contract — observes pipeline execution lifecycle.

Observers are notified of key lifecycle events during pipeline
execution. Multiple observers can be registered with the pipeline
to enable logging, metrics, auditing, and event emission.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.step import ExecutionStep
    from app.evaluation.execution.results.results import (
        ExecutionResult,
        StageResult,
        StepResult,
    )


class ExecutionObserver(ABC):
    """Contract for observing pipeline execution lifecycle.

    All observer methods are fire-and-forget — they should not
    affect execution flow.
    """

    @abstractmethod
    async def on_execution_started(self, context: PipelineContext) -> None:
        """Called when pipeline execution begins.

        Args:
            context: The pipeline context.

        """
        ...

    @abstractmethod
    async def on_stage_started(self, stage_name: str, total_steps: int) -> None:
        """Called when a stage begins execution.

        Args:
            stage_name: Name of the stage.
            total_steps: Number of steps in this stage.

        """
        ...

    @abstractmethod
    async def on_stage_completed(self, result: StageResult) -> None:
        """Called when a stage finishes execution.

        Args:
            result: The stage result.

        """
        ...

    @abstractmethod
    async def on_step_completed(self, result: StepResult) -> None:
        """Called when a step finishes execution.

        Args:
            result: The step result.

        """
        ...

    @abstractmethod
    async def on_execution_finished(self, result: ExecutionResult) -> None:
        """Called when pipeline execution finishes.

        Args:
            result: The overall execution result.

        """
        ...

    @abstractmethod
    async def on_execution_failed(self, result: ExecutionResult) -> None:
        """Called when pipeline execution fails.

        Args:
            result: The (failed) execution result.

        """
        ...
