"""Execution step — the smallest executable unit in the pipeline.

Steps are immutable, have explicit dependencies, carry retry metadata,
and are independently schedulable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import TYPE_CHECKING

from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from collections.abc import Sequence


@unique
class StepStatus(Enum):
    """Status of a single execution step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self in _STEP_TERMINAL_STATES


_STEP_TERMINAL_STATES: frozenset[StepStatus] = frozenset({
    StepStatus.COMPLETED,
    StepStatus.FAILED,
    StepStatus.SKIPPED,
})


@unique
class DependencyType(Enum):
    """Type of dependency between steps."""

    HARD = "hard"  # Must complete before dependent step can start
    SOFT = "soft"  # Should complete before, but dependent can proceed


@dataclass(frozen=True, slots=True)
class StepDependency:
    """A single dependency on another step."""

    step_id: UUIDv7
    dependency_type: DependencyType = DependencyType.HARD

    def __post_init__(self) -> None:
        """Validate dependency invariants."""
        if self.dependency_type == DependencyType.SOFT:
            # Soft dependencies are informational only
            pass


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    """The smallest executable unit in the pipeline.

    Each step represents a single unit of work — for example,
    invoking a provider for one item, computing one metric on
    one response, or persisting one result.

    Steps are immutable and designed to be deterministically
    scheduled and retried.
    """

    step_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    stage_type: StageType = StageType.PLANNING
    name: str = ""
    item_index: int | None = None
    dependencies: tuple[StepDependency, ...] = ()
    max_retries: int = 0
    timeout_seconds: int | None = None
    priority: int = 0
    order: int = 0
    metadata: dict[str, str] = field(default_factory=dict)

    # ── computed properties ────────────────────────────────────

    @property
    def has_dependencies(self) -> bool:
        """Return True if this step depends on other steps."""
        return len(self.dependencies) > 0

    @property
    def hard_dependency_ids(self) -> tuple[UUIDv7, ...]:
        """Return IDs of hard (blocking) dependencies."""
        return tuple(
            dep.step_id
            for dep in self.dependencies
            if dep.dependency_type == DependencyType.HARD
        )

    @property
    def soft_dependency_ids(self) -> tuple[UUIDv7, ...]:
        """Return IDs of soft (non-blocking) dependencies."""
        return tuple(
            dep.step_id
            for dep in self.dependencies
            if dep.dependency_type == DependencyType.SOFT
        )

    @property
    def all_dependency_ids(self) -> tuple[UUIDv7, ...]:
        """Return IDs of all dependencies."""
        return tuple(dep.step_id for dep in self.dependencies)

    @property
    def requires_retry(self) -> bool:
        """Return True if this step supports retry."""
        return self.max_retries > 0

    # ── factory helpers ─────────────────────────────────────────

    @classmethod
    def create(
        cls,
        stage_type: StageType,
        name: str,
        *,
        item_index: int | None = None,
        dependencies: Sequence[StepDependency] | None = None,
        max_retries: int = 0,
        timeout_seconds: int | None = None,
        priority: int = 0,
        order: int = 0,
        metadata: dict[str, str] | None = None,
    ) -> ExecutionStep:
        """Create a new execution step with sensible defaults.

        Args:
            stage_type: The stage this step belongs to.
            name: Human-readable step name.
            item_index: Optional dataset item index.
            dependencies: Optional dependency list.
            max_retries: Maximum retry attempts.
            timeout_seconds: Per-step timeout.
            priority: Execution priority (higher = more urgent).
            order: Ordering hint within the stage.
            metadata: Optional key-value metadata.

        Returns:
            A new ExecutionStep instance.

        """
        return cls(
            stage_type=stage_type,
            name=name,
            item_index=item_index,
            dependencies=tuple(dependencies) if dependencies else (),
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            priority=priority,
            order=order,
            metadata=metadata or {},
        )
