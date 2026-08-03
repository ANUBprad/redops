"""Domain enums for the Evaluation engine."""

from __future__ import annotations

from enum import Enum, unique


@unique
class RunStatus(Enum):
    """Lifecycle status of an evaluation run."""

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
        return self == RunStatus.COMPLETED


_TERMINAL_STATES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.TIMEDOUT,
        RunStatus.CANCELLED,
    }
)

_ACTIVE_STATES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.STARTING,
        RunStatus.RUNNING,
        RunStatus.PAUSED,
        RunStatus.CANCELLING,
    }
)


@unique
class ItemStatus(Enum):
    """Status of a single evaluation item."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self in _ITEM_TERMINAL_STATES


_ITEM_TERMINAL_STATES: frozenset[ItemStatus] = frozenset(
    {
        ItemStatus.COMPLETED,
        ItemStatus.FAILED,
        ItemStatus.SKIPPED,
        ItemStatus.CANCELLED,
    }
)


@unique
class EvaluationStatus(Enum):
    """Lifecycle status of an evaluation definition."""

    DRAFT = "draft"
    READY = "ready"
    ARCHIVED = "archived"

    @property
    def is_editable(self) -> bool:
        """Return True if the evaluation can be modified."""
        return self == EvaluationStatus.DRAFT

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self == EvaluationStatus.ARCHIVED


@unique
class EvaluationType(Enum):
    """Type of evaluation determining execution behavior."""

    SINGLE = "single"
    DATASET = "dataset"
    REGRESSION = "regression"
    SAFETY = "safety"
    RAG = "rag"
    COMPARISON = "comparison"


@unique
class FailureReason(Enum):
    """Categorized reason for item or run failure."""

    PROVIDER_ERROR = "provider_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_MODEL = "invalid_model"
    CONTEXT_WINDOW_EXCEEDED = "context_window_exceeded"
    TOKEN_LIMIT_EXCEEDED = "token_limit_exceeded"
    INVALID_RESPONSE = "invalid_response"
    VALIDATION_ERROR = "validation_error"
    METRIC_COMPUTATION_ERROR = "metric_computation_error"
    CONFIGURATION_ERROR = "configuration_error"
    DATASET_ERROR = "dataset_error"
    INTERNAL_ERROR = "internal_error"
    CANCELLED = "cancelled"

    @property
    def is_retryable(self) -> bool:
        """Return True if this failure reason warrants a retry."""
        return self in _RETRYABLE_FAILURES


_RETRYABLE_FAILURES: frozenset[FailureReason] = frozenset(
    {
        FailureReason.PROVIDER_TIMEOUT,
        FailureReason.PROVIDER_UNAVAILABLE,
        FailureReason.RATE_LIMITED,
    }
)


@unique
class CancellationReason(Enum):
    """Reason an evaluation run was cancelled."""

    USER_CANCELLED = "user_cancelled"
    SYSTEM_CANCELLED = "system_cancelled"
    QUOTA_EXCEEDED = "quota_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    DEPLOYMENT_CANCELLED = "deployment_cancelled"


@unique
class Priority(Enum):
    """Execution priority for evaluation runs."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def numeric(self) -> int:
        """Return numeric weight for ordering."""
        return _PRIORITY_WEIGHTS[self]


_PRIORITY_WEIGHTS: dict[Priority, int] = {
    Priority.LOW: 0,
    Priority.NORMAL: 1,
    Priority.HIGH: 2,
    Priority.CRITICAL: 3,
}
