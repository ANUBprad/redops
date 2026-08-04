"""Unified AI execution enums.

Single source of truth for run lifecycle, step/item status,
failure classification, cancellation reasons, and priority levels.
Used by evaluation, agent runtime, and red team bounded contexts.
"""

from __future__ import annotations

from enum import Enum, unique

# ── Run Lifecycle ──────────────────────────────────────────────


@unique
class RunStatus(Enum):
    """Lifecycle status of any AI execution run.

    Shared across evaluation runs, agent runs, and attack runs.
    """

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


# ── Step / Item Status ────────────────────────────────────────


@unique
class StepStatus(Enum):
    """Status of a single execution step or evaluation item.

    Superset covering both agent steps (which support RETRYING)
    and evaluation items. SKIPPED and CANCELLED are terminal.
    """

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


# ── Failure Classification ────────────────────────────────────


@unique
class FailureReason(Enum):
    """Categorized reason for step, item, or run failure.

    Superset covering evaluation-specific (METRIC_COMPUTATION_ERROR,
    DATASET_ERROR, INVALID_RESPONSE) and agent-specific
    (TOOL_EXECUTION_ERROR, ORCHESTRATION_ERROR, CHECKPOINT_ERROR,
    TIMEOUT_EXCEEDED) failure modes.
    """

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
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    ORCHESTRATION_ERROR = "orchestration_error"
    CHECKPOINT_ERROR = "checkpoint_error"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
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
        FailureReason.TOOL_EXECUTION_ERROR,
    }
)


# ── Cancellation ──────────────────────────────────────────────


@unique
class CancellationReason(Enum):
    """Reason a run was cancelled.

    Superset covering evaluation (DEPLOYMENT_CANCELLED) and
    agent (TIMEOUT_EXCEEDED) cancellation reasons.
    """

    USER_CANCELLED = "user_cancelled"
    SYSTEM_CANCELLED = "system_cancelled"
    QUOTA_EXCEEDED = "quota_exceeded"
    BUDGET_EXCEEDED = "budget_exceeded"
    DEPLOYMENT_CANCELLED = "deployment_cancelled"
    TIMEOUT_EXCEEDED = "timeout_exceeded"


# ── Priority ──────────────────────────────────────────────────


@unique
class Priority(Enum):
    """Execution priority for AI runs.

    Shared across evaluation runs and agent runs.
    """

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
