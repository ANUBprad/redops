"""Execution-level domain events.

These events describe the lifecycle of pipeline execution.
They are raised by the pipeline infrastructure and published
via the domain EventPublisher contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7


@dataclass(frozen=True, slots=True)
class ExecutionPlanned:
    """Raised when an execution plan is created."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    plan_id: UUIDv7 = field(default_factory=UUIDv7)
    plan_version: int = 1
    total_stages: int = 0
    total_steps: int = 0
    total_items: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.planned"


@dataclass(frozen=True, slots=True)
class PipelineBuilt:
    """Raised when an execution pipeline is built from a plan."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    plan_id: UUIDv7 = field(default_factory=UUIDv7)
    plan_version: int = 1
    stage_count: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.pipeline.built"


@dataclass(frozen=True, slots=True)
class StageStarted:
    """Raised when a pipeline stage begins execution."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    stage_type: StageType = StageType.PLANNING
    stage_name: str = ""
    total_steps: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.stage.started"


@dataclass(frozen=True, slots=True)
class StageCompleted:
    """Raised when a pipeline stage completes successfully."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    stage_type: StageType = StageType.PLANNING
    stage_name: str = ""
    duration_ms: int = 0
    steps_succeeded: int = 0
    steps_failed: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.stage.completed"


@dataclass(frozen=True, slots=True)
class StageFailed:
    """Raised when a pipeline stage fails irrecoverably."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    stage_type: StageType = StageType.PLANNING
    stage_name: str = ""
    error_message: str = ""
    duration_ms: int = 0
    steps_succeeded: int = 0
    steps_failed: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.stage.failed"


@dataclass(frozen=True, slots=True)
class ExecutionPaused:
    """Raised when pipeline execution is paused."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    current_stage: StageType = StageType.PLANNING
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.paused"


@dataclass(frozen=True, slots=True)
class ExecutionResumed:
    """Raised when paused execution is resumed."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    current_stage: StageType = StageType.PLANNING
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.resumed"


@dataclass(frozen=True, slots=True)
class ExecutionFinished:
    """Raised when pipeline execution completes successfully."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    total_duration_ms: int = 0
    stages_succeeded: int = 0
    stages_total: int = 0
    items_succeeded: int = 0
    items_failed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.finished"


@dataclass(frozen=True, slots=True)
class ExecutionAborted:
    """Raised when pipeline execution is aborted (cancelled or failed)."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    reason: str = ""
    is_cancellation: bool = False
    total_duration_ms: int = 0
    stages_succeeded: int = 0
    stages_total: int = 0
    items_completed: int = 0
    items_total: int = 0

    @property
    def event_type(self) -> str:
        """Return event type identifier."""
        return "execution.aborted"
