"""Domain events for the Agent Runtime engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.agents.domain.enums.agent_enums import (
    AgentCancellationReason,
    AgentRunFailureReason,
)
from app.kernel.entities.base import DomainEvent, UUIDv7


@dataclass(frozen=True, slots=True)
class AgentRunCreated(DomainEvent):
    """Raised when an agent run is created."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    agent_name: str = ""
    provider_name: str = ""
    model_id: str = ""

    @property
    def event_type(self) -> str:
        return "agents.run.created"


@dataclass(frozen=True, slots=True)
class AgentRunQueued(DomainEvent):
    """Raised when an agent run enters the QUEUED state."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    agent_name: str = ""
    priority: str = ""

    @property
    def event_type(self) -> str:
        return "agents.run.queued"


@dataclass(frozen=True, slots=True)
class AgentRunStarted(DomainEvent):
    """Raised when an agent run begins execution."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    provider_name: str = ""
    model_id: str = ""
    total_steps: int = 0

    @property
    def event_type(self) -> str:
        return "agents.run.started"


@dataclass(frozen=True, slots=True)
class AgentRunCompleted(DomainEvent):
    """Raised when an agent run finishes successfully."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    steps_completed: int = 0
    steps_total: int = 0
    duration_ms: int = 0

    @property
    def event_type(self) -> str:
        return "agents.run.completed"


@dataclass(frozen=True, slots=True)
class AgentRunFailed(DomainEvent):
    """Raised when an agent run fails irrecoverably."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    error_code: str = ""
    error_message: str = ""
    steps_completed: int = 0
    steps_total: int = 0

    @property
    def event_type(self) -> str:
        return "agents.run.failed"


@dataclass(frozen=True, slots=True)
class AgentRunCancelled(DomainEvent):
    """Raised when an agent run is cancelled."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    reason: AgentCancellationReason = AgentCancellationReason.USER_CANCELLED
    force: bool = False
    steps_completed: int = 0
    steps_total: int = 0

    @property
    def event_type(self) -> str:
        return "agents.run.cancelled"


@dataclass(frozen=True, slots=True)
class AgentRunTimedOut(DomainEvent):
    """Raised when an agent run exceeds its maximum duration."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    timeout_seconds: int = 0
    steps_completed: int = 0
    steps_total: int = 0

    @property
    def event_type(self) -> str:
        return "agents.run.timed_out"


@dataclass(frozen=True, slots=True)
class AgentStepStarted(DomainEvent):
    """Raised when an agent step begins execution."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    step_id: str = ""
    step_index: int = 0
    tool_name: str = ""

    @property
    def event_type(self) -> str:
        return "agents.step.started"


@dataclass(frozen=True, slots=True)
class AgentStepCompleted(DomainEvent):
    """Raised when an agent step finishes successfully."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    step_id: str = ""
    step_index: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0

    @property
    def event_type(self) -> str:
        return "agents.step.completed"


@dataclass(frozen=True, slots=True)
class AgentStepFailed(DomainEvent):
    """Raised when an agent step fails."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    step_id: str = ""
    step_index: int = 0
    error_code: str = ""
    error_message: str = ""
    failure_reason: AgentRunFailureReason = AgentRunFailureReason.INTERNAL_ERROR
    retry_count: int = 0

    @property
    def event_type(self) -> str:
        return "agents.step.failed"


@dataclass(frozen=True, slots=True)
class AgentCheckpointCreated(DomainEvent):
    """Raised when a checkpoint is persisted."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    checkpoint_number: int = 0
    steps_completed: int = 0

    @property
    def event_type(self) -> str:
        return "agents.checkpoint.created"


@dataclass(frozen=True, slots=True)
class AgentCheckpointLoaded(DomainEvent):
    """Raised when a checkpoint is loaded for resume."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    checkpoint_number: int = 0
    steps_completed: int = 0

    @property
    def event_type(self) -> str:
        return "agents.checkpoint.loaded"
