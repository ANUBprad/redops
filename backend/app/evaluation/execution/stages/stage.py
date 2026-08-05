"""Abstract pipeline stage definitions.

Each stage represents a phase of the execution pipeline.
Stages are composable, ordered, and support validation,
execution, rollback, and resume capabilities.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, unique
from typing import TYPE_CHECKING, Any

from app.evaluation.execution.stages.types import StageType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.execution.context.context import PipelineContext
    from app.evaluation.execution.pipeline.step import ExecutionStep
    from app.evaluation.execution.results.results import StageResult


class ExecutionStage(ABC):
    """Abstract base for a single pipeline execution stage.

    Each stage defines three lifecycle methods — validate, execute,
    rollback — plus supports_resume which tells the orchestrator
    whether the stage can be resumed from a checkpoint.

    Stages are reference-types (not frozen) because they may hold
    transient state during execution. The *definition* of a stage
    (its type, name, order, dependencies) is immutable.
    """

    def __init__(self, stage_type: StageType, name: str) -> None:
        """Initialize an execution stage.

        Args:
            stage_type: The categorised type of this stage.
            name: Human-readable stage name.

        """
        self._stage_type = stage_type
        self._name = name

    # ── identity ────────────────────────────────────────────────

    @property
    def stage_type(self) -> StageType:
        """Return the categorised stage type."""
        return self._stage_type

    @property
    def name(self) -> str:
        """Return the human-readable stage name."""
        return self._name

    @property
    def order(self) -> int:
        """Return the canonical execution order."""
        return self._stage_type.order

    # ── lifecycle ───────────────────────────────────────────────

    @abstractmethod
    def validate(self, context: PipelineContext) -> list[ValidationIssue]:
        """Validate that the stage can execute given the context.

        Args:
            context: The immutable pipeline context.

        Returns:
            A list of validation issues. An empty list means valid.

        """
        ...

    @abstractmethod
    async def execute(
        self,
        context: PipelineContext,
        steps: Sequence[ExecutionStep],
        shared_state: dict[str, Any] | None = None,
    ) -> StageResult:
        """Execute the stage with the given context and steps.

        Args:
            context: The immutable pipeline context.
            steps: The steps assigned to this stage.
            shared_state: Mutable dict for passing data between stages.

        Returns:
            The result of stage execution.

        """
        ...

    @abstractmethod
    async def rollback(
        self,
        context: PipelineContext,
        result: StageResult,
    ) -> None:
        """Roll back any side-effects from a failed stage execution.

        Args:
            context: The immutable pipeline context.
            result: The (failed) stage result to roll back from.

        """
        ...

    # ── capabilities ────────────────────────────────────────────

    @abstractmethod
    def supports_resume(self) -> bool:
        """Return True if this stage can be resumed from a checkpoint."""
        ...

    # ── equality / identity ─────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExecutionStage):
            return NotImplemented
        return self._stage_type == other._stage_type and self._name == other._name

    def __hash__(self) -> int:
        return hash((self._stage_type, self._name))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(stage_type={self._stage_type.value}, name={self._name!r})"


@unique
class ValidationSeverity(Enum):
    """Severity of a validation issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue:
    """A single validation issue found during stage validation."""

    def __init__(
        self,
        message: str,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
        *,
        code: str = "",
        field: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a validation issue.

        Args:
            message: Human-readable description.
            severity: Severity level.
            code: Machine-readable error code.
            field: Optional field reference.
            details: Optional structured details.

        """
        self.message = message
        self.severity = severity
        self.code = code
        self.field = field
        self.details = details or {}

    def __repr__(self) -> str:
        return (
            f"ValidationIssue(severity={self.severity.value}, "
            f"code={self.code!r}, message={self.message!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValidationIssue):
            return NotImplemented
        return (
            self.message == other.message
            and self.severity == other.severity
            and self.code == other.code
        )

    def __hash__(self) -> int:
        return hash((self.message, self.severity, self.code))
