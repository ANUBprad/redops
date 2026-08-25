"""Domain-level execution result types.

These types describe what happened during execution without
referencing any infrastructure or concrete executor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique

from app.evaluation.execution.pipeline.step import StepStatus
from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7


@unique
class ExecutionOutcome(Enum):
    """Overall outcome of an execution unit."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class StepResult:
    """Result of executing a single step."""

    step_id: UUIDv7
    step_name: str
    stage_type: StageType
    status: StepStatus
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCESS
    duration_ms: int = 0
    error: str | None = None
    retry_count: int = 0
    metadata: dict[str, str] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_success(self) -> bool:
        """Return True if the step completed successfully."""
        return self.outcome == ExecutionOutcome.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Return True if the step failed."""
        return self.outcome == ExecutionOutcome.FAILURE


@dataclass(frozen=True, slots=True)
class StageResult:
    """Result of executing an entire stage."""

    stage_type: StageType
    stage_name: str
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCESS
    step_results: tuple[StepResult, ...] = ()
    duration_ms: int = 0
    error: str | None = None
    items_processed: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def is_success(self) -> bool:
        """Return True if the stage completed successfully."""
        return self.outcome == ExecutionOutcome.SUCCESS

    @property
    def total_steps(self) -> int:
        """Return total number of step results."""
        return len(self.step_results)

    @property
    def successful_steps(self) -> list[StepResult]:
        """Return step results that succeeded."""
        return [sr for sr in self.step_results if sr.is_success]

    @property
    def failed_steps(self) -> list[StepResult]:
        """Return step results that failed."""
        return [sr for sr in self.step_results if sr.is_failure]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Overall result of a pipeline execution."""

    run_id: UUIDv7
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCESS
    stage_results: tuple[StageResult, ...] = ()
    total_duration_ms: int = 0
    total_items: int = 0
    items_processed: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def is_success(self) -> bool:
        """Return True if the overall execution was successful."""
        return self.outcome == ExecutionOutcome.SUCCESS

    @property
    def total_stages(self) -> int:
        """Return total number of stage results."""
        return len(self.stage_results)

    @property
    def successful_stages(self) -> list[StageResult]:
        """Return stage results that succeeded."""
        return [sr for sr in self.stage_results if sr.is_success]

    @property
    def failed_stages(self) -> list[StageResult]:
        """Return stage results that failed."""
        return [sr for sr in self.stage_results if not sr.is_success]
