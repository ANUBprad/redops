"""Runtime domain events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.kernel.entities.base import UUIDv7


@dataclass(frozen=True, slots=True)
class ExecutionRequested:
    """Raised when an execution request is received."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    provider_name: str = ""
    model_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.execution.requested"


@dataclass(frozen=True, slots=True)
class ExecutionStarted:
    """Raised when execution begins."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    provider_name: str = ""
    model_id: str = ""

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.execution.started"


@dataclass(frozen=True, slots=True)
class ExecutionCompleted:
    """Raised when execution finishes successfully."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    provider_name: str = ""
    model_id: str = ""
    latency_ms: float = 0.0

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.execution.completed"


@dataclass(frozen=True, slots=True)
class ExecutionFailed:
    """Raised when execution fails."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    provider_name: str = ""
    model_id: str = ""
    error_code: str = ""
    error_message: str = ""

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.execution.failed"


@dataclass(frozen=True, slots=True)
class RetryScheduled:
    """Raised when a retry is scheduled."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    attempt: int = 0
    delay_seconds: float = 0.0

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.retry.scheduled"


@dataclass(frozen=True, slots=True)
class RetrySucceeded:
    """Raised when a retry succeeds."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    attempt: int = 0

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.retry.succeeded"


@dataclass(frozen=True, slots=True)
class RetryExhausted:
    """Raised when all retries are exhausted."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    total_attempts: int = 0

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.retry.exhausted"


@dataclass(frozen=True, slots=True)
class CircuitOpened:
    """Raised when circuit breaker opens."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    provider_name: str = ""
    failure_count: int = 0

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.circuit.opened"


@dataclass(frozen=True, slots=True)
class CircuitClosed:
    """Raised when circuit breaker closes."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    provider_name: str = ""

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.circuit.closed"


@dataclass(frozen=True, slots=True)
class ProviderFallbackStarted:
    """Raised when fallback to another provider begins."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    original_provider: str = ""
    fallback_provider: str = ""

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.fallback.started"


@dataclass(frozen=True, slots=True)
class ProviderFallbackSucceeded:
    """Raised when fallback provider succeeds."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    fallback_provider: str = ""

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.fallback.succeeded"


@dataclass(frozen=True, slots=True)
class TimeoutExceeded:
    """Raised when execution timeout is exceeded."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    timeout_seconds: float = 0.0

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.timeout.exceeded"


@dataclass(frozen=True, slots=True)
class BudgetExceeded:
    """Raised when execution budget is exceeded."""

    event_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = None
    request_id: UUIDv7 = field(default_factory=UUIDv7)
    budget_type: str = ""
    limit: float = 0.0
    current: float = 0.0

    @property
    def event_type(self) -> str:
        """Return event type."""
        return "runtime.budget.exceeded"
