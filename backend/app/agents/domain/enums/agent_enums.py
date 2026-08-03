"""Domain enums for the Agent Runtime engine."""

from __future__ import annotations

from enum import Enum, unique


@unique
class AgentRunStatus(Enum):
    """Lifecycle status of an agent run."""

    CREATED = "created"
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEDOUT = "timedout"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self in _TERMINAL_STATES

    @property
    def is_active(self) -> bool:
        """Return True if the run is actively executing."""
        return self in _ACTIVE_STATES

    @property
    def is_success(self) -> bool:
        """Return True if the run completed successfully."""
        return self == AgentRunStatus.COMPLETED


_TERMINAL_STATES: frozenset[AgentRunStatus] = frozenset(
    {
        AgentRunStatus.COMPLETED,
        AgentRunStatus.FAILED,
        AgentRunStatus.TIMEDOUT,
        AgentRunStatus.CANCELLED,
    }
)

_ACTIVE_STATES: frozenset[AgentRunStatus] = frozenset(
    {
        AgentRunStatus.STARTING,
        AgentRunStatus.RUNNING,
        AgentRunStatus.PAUSED,
        AgentRunStatus.CANCELLING,
    }
)


@unique
class StepStatus(Enum):
    """Status of a single agent step."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self in _STEP_TERMINAL_STATES


_STEP_TERMINAL_STATES: frozenset[StepStatus] = frozenset(
    {
        StepStatus.COMPLETED,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
        StepStatus.CANCELLED,
    }
)


@unique
class AgentRunFailureReason(Enum):
    """Categorized reason for step or run failure."""

    PROVIDER_ERROR = "provider_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_MODEL = "invalid_model"
    CONTEXT_WINDOW_EXCEEDED = "context_window_exceeded"
    TOKEN_LIMIT_EXCEEDED = "token_limit_exceeded"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    ORCHESTRATION_ERROR = "orchestration_error"
    CHECKPOINT_ERROR = "checkpoint_error"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
    CONFIGURATION_ERROR = "configuration_error"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"
    CANCELLED = "cancelled"

    @property
    def is_retryable(self) -> bool:
        """Return True if this failure reason warrants a retry."""
        return self in _RETRYABLE_FAILURES


_RETRYABLE_FAILURES: frozenset[AgentRunFailureReason] = frozenset(
    {
        AgentRunFailureReason.PROVIDER_TIMEOUT,
        AgentRunFailureReason.PROVIDER_UNAVAILABLE,
        AgentRunFailureReason.RATE_LIMITED,
        AgentRunFailureReason.TOOL_EXECUTION_ERROR,
    }
)


@unique
class AgentCancellationReason(Enum):
    """Reason an agent run was cancelled."""

    USER_CANCELLED = "user_cancelled"
    SYSTEM_CANCELLED = "system_cancelled"
    QUOTA_EXCEEDED = "quota_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT_EXCEEDED = "timeout_exceeded"


@unique
class AgentRunPriority(Enum):
    """Execution priority for agent runs."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        """Return numeric weight for ordering."""
        return _PRIORITY_WEIGHTS[self]


_PRIORITY_WEIGHTS: dict[AgentRunPriority, int] = {
    AgentRunPriority.LOW: 0,
    AgentRunPriority.NORMAL: 1,
    AgentRunPriority.HIGH: 2,
    AgentRunPriority.CRITICAL: 3,
}
