"""Runtime circuit breaker — provider-agnostic circuit breaking."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum, unique


@unique
class RuntimeCircuitState(Enum):
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

    state: RuntimeCircuitState
    failure_count: int
    success_count: int
    last_failure_time: datetime | None
    last_state_change: datetime
    total_rejected: int


@dataclass(frozen=True, slots=True)
class ProbeAdmission:
    """Result of a HALF_OPEN-aware admission request.

    Attributes:
        admitted: Whether the caller may invoke the provider.
        generation: Breaker episode the decision belongs to. Completions
            must present it back so stale probes cannot corrupt a newer
            episode.
        reserved: True when a HALF_OPEN probe slot was reserved and must
            be released via record_success/record_failure/release_probe.
        exhausted: True when denied specifically because HALF_OPEN probe
            capacity is exhausted (vs. the breaker being OPEN).

    """

    admitted: bool
    generation: int = 0
    reserved: bool = False
    exhausted: bool = False


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
        self._state = RuntimeCircuitState.CLOSED
        self._metrics = CircuitBreakerMetrics()
        # Rolling failure timestamps for the configured window. Bounded:
        # pruned to the window on every record and capped at the threshold,
        # which is all the OPEN decision ever needs.
        self._failure_window: deque[datetime] = deque()
        # HALF_OPEN probe admission state. Every state transition starts a
        # new generation (episode); completions presenting a stale
        # generation are ignored so late probes cannot corrupt the new
        # episode. ponytail: in-process only; multi-worker deployments
        # need a shared breaker to coordinate globally.
        self._generation = 0
        self._half_open_in_flight = 0

    @property
    def state(self) -> RuntimeCircuitState:
        """Return current circuit state."""
        self._evaluate_state()
        return self._state

    @property
    def half_open_in_flight(self) -> int:
        """Return the number of currently reserved HALF_OPEN probe slots."""
        return self._half_open_in_flight

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        self._evaluate_state()
        if self._state == RuntimeCircuitState.OPEN:
            self._metrics.total_rejected += 1
            return False
        return True

    def acquire(self) -> ProbeAdmission:
        """Admit one provider invocation, reserving a HALF_OPEN probe slot.

        The check and the reservation run back-to-back with no await
        between, so concurrent coroutines cannot exceed
        ``half_open_max_calls`` within one event loop. CLOSED admissions
        reserve nothing; OPEN and exhausted admissions reserve nothing.
        """
        self._evaluate_state()
        if self._state == RuntimeCircuitState.OPEN:
            self._metrics.total_rejected += 1
            return ProbeAdmission(admitted=False, generation=self._generation)
        if self._state == RuntimeCircuitState.HALF_OPEN:
            if self._half_open_in_flight >= self._config.half_open_max_calls:
                self._metrics.total_rejected += 1
                return ProbeAdmission(
                    admitted=False,
                    generation=self._generation,
                    exhausted=True,
                )
            self._half_open_in_flight += 1
            return ProbeAdmission(
                admitted=True,
                generation=self._generation,
                reserved=True,
            )
        return ProbeAdmission(admitted=True, generation=self._generation)

    def release_probe(self, generation: int) -> None:
        """Release a reserved HALF_OPEN probe slot without recording.

        Used for completions that must not mutate breaker accounting
        (fatal errors, cancellation). Stale generations are ignored:
        their episode already cleared the reservation.
        """
        if generation == self._generation and self._half_open_in_flight > 0:
            self._half_open_in_flight -= 1

    def _is_stale(self, generation: int | None) -> bool:
        """Return True when a completion belongs to a superseded episode."""
        return generation is not None and generation != self._generation

    def _release_if_current(self, generation: int | None) -> None:
        """Release one reserved slot for a current-episode completion."""
        if generation is not None and generation == self._generation:
            if self._half_open_in_flight > 0:
                self._half_open_in_flight -= 1

    def record_success(self, generation: int | None = None) -> RuntimeCircuitState:
        """Record a successful execution.

        A reserved probe presents its admission generation: stale
        completions are ignored and the slot is released for current
        ones before counting.
        """
        if self._is_stale(generation):
            return self._state
        self._release_if_current(generation)
        self._metrics.success_count += 1
        self._metrics.consecutive_successes += 1

        if (
            self._state == RuntimeCircuitState.HALF_OPEN
            and self._metrics.consecutive_successes >= self._config.success_threshold
        ):
            self._transition_to(RuntimeCircuitState.CLOSED)
            self._metrics.reset()

        return self._state

    def record_failure(self, generation: int | None = None) -> RuntimeCircuitState:
        """Record a failed execution.

        Only failures inside the rolling ``failure_window_seconds`` count
        toward the threshold; older failures age out. A failed HALF_OPEN
        probe always reopens immediately. Stale reserved completions are
        ignored.
        """
        if self._is_stale(generation):
            return self._state
        self._release_if_current(generation)
        now = datetime.now(UTC)
        self._metrics.failure_count += 1
        self._metrics.last_failure_time = now
        self._metrics.consecutive_successes = 0

        window_start = now - timedelta(seconds=self._config.failure_window_seconds)
        while self._failure_window and self._failure_window[0] < window_start:
            self._failure_window.popleft()
        self._failure_window.append(now)
        while len(self._failure_window) > self._config.failure_threshold:
            self._failure_window.popleft()

        if self._state == RuntimeCircuitState.HALF_OPEN:  # noqa: SIM114
            self._transition_to(RuntimeCircuitState.OPEN)
        elif (
            self._state == RuntimeCircuitState.CLOSED
            and len(self._failure_window) >= self._config.failure_threshold
        ):
            self._transition_to(RuntimeCircuitState.OPEN)

        return self._state

    def reset(self) -> None:
        """Manually reset circuit breaker to CLOSED."""
        self._transition_to(RuntimeCircuitState.CLOSED)
        self._metrics.reset()
        self._failure_window.clear()

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
        if self._state != RuntimeCircuitState.OPEN:
            return

        if self._metrics.last_state_change is None:
            return

        elapsed = (datetime.now(UTC) - self._metrics.last_state_change).total_seconds()
        if elapsed >= self._config.recovery_timeout_seconds:
            self._transition_to(RuntimeCircuitState.HALF_OPEN)

    def _transition_to(self, new_state: RuntimeCircuitState) -> None:
        """Transition to a new state.

        Every transition starts a new generation: reserved slots belong
        to the superseded episode and their late completions are
        ignored. Entering OPEN or CLOSED additionally starts a fresh
        failure episode: stale window entries must not haunt it.
        """
        self._state = new_state
        self._generation += 1
        self._metrics.last_state_change = datetime.now(UTC)
        if new_state in (RuntimeCircuitState.OPEN, RuntimeCircuitState.CLOSED):
            self._failure_window.clear()
        # Any in-flight count at a transition boundary belongs to the
        # superseded episode (slots only exist in HALF_OPEN, which always
        # exits through here): never carry it into the new episode.
        self._half_open_in_flight = 0
