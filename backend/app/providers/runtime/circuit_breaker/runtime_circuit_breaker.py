"""Runtime circuit breaker — provider-agnostic circuit breaking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique


@unique
class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    """Immutable circuit breaker configuration.

    Attributes:
        failure_threshold: Failures before opening circuit.
        recovery_timeout_seconds: Time before attempting half-open.
        half_open_max_calls: Max calls in half-open state.
        success_threshold: Successes in half-open to close circuit.
        failure_window_seconds: Window for counting failures.

    """

    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_max_calls: int = 1
    success_threshold: int = 1
    failure_window_seconds: float = 60.0


@dataclass
class CircuitBreakerMetrics:
    """Mutable metrics tracked by the circuit breaker.

    Not frozen — these are internal counters.

    """

    failure_count: int = 0
    success_count: int = 0
    consecutive_successes: int = 0
    last_failure_time: datetime | None = None
    last_state_change: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_rejected: int = 0

    def reset(self) -> None:
        """Reset all counters."""
        self.failure_count = 0
        self.success_count = 0
        self.consecutive_successes = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CircuitBreakerSnapshot:
    """Immutable snapshot of circuit breaker state."""

    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: datetime | None
    last_state_change: datetime
    total_rejected: int


class RuntimeCircuitBreaker:
    """Provider-agnostic circuit breaker.

    State machine: CLOSED → OPEN → HALF_OPEN → CLOSED

    Usage:
        cb = RuntimeCircuitBreaker(config)
        if cb.can_execute():
            result = await do_something()
            cb.record_success()
        else:
            raise CircuitBreakerOpenError(...)

    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        """Initialize circuit breaker."""
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._metrics = CircuitBreakerMetrics()

    @property
    def state(self) -> CircuitState:
        """Return current circuit state."""
        self._evaluate_state()
        return self._state

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        self._evaluate_state()
        if self._state == CircuitState.OPEN:
            self._metrics.total_rejected += 1
            return False
        return True

    def record_success(self) -> CircuitState:
        """Record a successful execution."""
        self._metrics.success_count += 1
        self._metrics.consecutive_successes += 1

        if (
            self._state == CircuitState.HALF_OPEN
            and self._metrics.consecutive_successes >= self._config.success_threshold
        ):
            self._transition_to(CircuitState.CLOSED)
            self._metrics.reset()

        return self._state

    def record_failure(self) -> CircuitState:
        """Record a failed execution."""
        now = datetime.now(UTC)
        self._metrics.failure_count += 1
        self._metrics.last_failure_time = now
        self._metrics.consecutive_successes = 0

        if self._state == CircuitState.HALF_OPEN:  # noqa: SIM114
            self._transition_to(CircuitState.OPEN)
        elif (
            self._state == CircuitState.CLOSED
            and self._metrics.failure_count >= self._config.failure_threshold
        ):
            self._transition_to(CircuitState.OPEN)

        return self._state

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED."""
        self._transition_to(CircuitState.CLOSED)
        self._metrics.reset()

    def snapshot(self) -> CircuitBreakerSnapshot:
        """Return immutable snapshot of current state."""
        self._evaluate_state()
        return CircuitBreakerSnapshot(
            state=self._state,
            failure_count=self._metrics.failure_count,
            success_count=self._metrics.success_count,
            last_failure_time=self._metrics.last_failure_time,
            last_state_change=self._metrics.last_state_change,
            total_rejected=self._metrics.total_rejected,
        )

    def _evaluate_state(self) -> None:
        """Evaluate and transition state if needed."""
        if self._state != CircuitState.OPEN:
            return

        if self._metrics.last_state_change is None:
            return

        elapsed = (datetime.now(UTC) - self._metrics.last_state_change).total_seconds()
        if elapsed >= self._config.recovery_timeout_seconds:
            self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        self._state = new_state
        self._metrics.last_state_change = datetime.now(UTC)
