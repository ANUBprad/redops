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


@dataclass(frozen=True, slots=True)
class FailureReport:
    """Detailed report of failures encountered during execution."""

    total_failures: int = 0
    step_failures: tuple[StepResult, ...] = ()
    stage_failures: tuple[StageResult, ...] = ()
    failure_reasons: dict[str, int] = field(default_factory=dict)
    first_failure_message: str | None = None
    last_failure_message: str | None = None

    @property
    def has_failures(self) -> bool:
        """Return True if any failures occurred."""
        return self.total_failures > 0


@dataclass(frozen=True, slots=True)
class ExecutionStatistics:
    """Aggregated statistics from pipeline execution."""

    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    total_duration_ms: int = 0
    total_retries: int = 0
    items_per_second: float = 0.0
    average_step_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Return the fraction of completed vs total steps."""
        if self.total_steps == 0:
            return 1.0
        return self.completed_steps / self.total_steps


@dataclass(frozen=True, slots=True)
class PipelineSummary:
    """High-level summary of a pipeline execution."""

    run_id: UUIDv7
    plan_version: int = 0
    outcome: ExecutionOutcome = ExecutionOutcome.SUCCESS
    total_duration_ms: int = 0
    total_items: int = 0
    items_processed: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    stages_completed: int = 0
    stages_total: int = 0
    statistics: ExecutionStatistics = field(default_factory=ExecutionStatistics)
    failure_report: FailureReport = field(default_factory=FailureReport)
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_success(self) -> bool:
        """Return True if the pipeline completed successfully."""
        return self.outcome == ExecutionOutcome.SUCCESS

    @classmethod
    def from_execution_result(
        cls,
        result: ExecutionResult,
        plan_version: int = 0,
        statistics: ExecutionStatistics | None = None,
        failure_report: FailureReport | None = None,
    ) -> PipelineSummary:
        """Create a summary from an execution result.

        Args:
            result: The execution result to summarise.
            plan_version: The plan version used.
            statistics: Optional pre-computed statistics.
            failure_report: Optional pre-computed failure report.

        Returns:
            A new PipelineSummary.

        """
        return cls(
            run_id=result.run_id,
            plan_version=plan_version,
            outcome=result.outcome,
            total_duration_ms=result.total_duration_ms,
            total_items=result.total_items,
            items_processed=result.items_processed,
            items_succeeded=result.items_succeeded,
            items_failed=result.items_failed,
            stages_completed=result.total_stages,
            stages_total=result.total_stages,
            statistics=statistics or ExecutionStatistics(),
            failure_report=failure_report or FailureReport(),
            completed_at=result.completed_at or datetime.now(UTC),
        )
