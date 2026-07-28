"""Circuit breaker abstraction for resilient external service calls.

The circuit breaker prevents cascading failures by detecting
when an external service is unhealthy and failing fast instead
of waiting for timeouts.

States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (probing)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = auto()
    """Normal operation — requests pass through."""

    OPEN = auto()
    """Failing — requests are rejected immediately."""

    HALF_OPEN = auto()
    """Probing — a limited number of requests pass through."""


class CircuitBreaker(ABC):
    """Abstract circuit breaker for protecting external service calls.

    Implementations track failure counts and transition between states.
    The circuit opens after a threshold of consecutive failures and
    half-opens after a recovery timeout to probe for recovery.
    """

    @abstractmethod
    async def call(
        self,
        operation: F,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute an operation through the circuit breaker.

        If the circuit is OPEN, the call is rejected immediately.
        If HALF_OPEN, the call is allowed but the result determines
        whether the circuit closes or stays open.

        Args:
            operation: The async callable to protect.
            *args: Positional arguments for the operation.
            **kwargs: Keyword arguments for the operation.

        Returns:
            The result of the operation.

        Raises:
            Exception: If the operation fails or the circuit is OPEN.

        """
        ...

    @property
    @abstractmethod
    def state(self) -> CircuitState:
        """Return the current circuit breaker state."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        ...


class InMemoryCircuitBreaker(CircuitBreaker):
    """In-memory implementation of the circuit breaker pattern.

    This is a concrete implementation suitable for single-process
    deployments. Distributed implementations (Redis-based) can
    be swapped in without changing call sites.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = timedelta(seconds=recovery_timeout_seconds)
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        # Check if we should transition from OPEN to HALF_OPEN
        if self._state is CircuitState.OPEN and self._last_failure_time is not None:
            if datetime.now(UTC) - self._last_failure_time >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    async def call(
        self,
        operation: F,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        match self.state:
            case CircuitState.OPEN:
                raise CircuitBreakerOpenError()

            case CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max_calls:
                    raise CircuitBreakerOpenError()
                self._half_open_calls += 1
                try:
                    result = await operation(*args, **kwargs)
                    self._on_success()
                    return result
                except Exception:
                    self._on_failure()
                    raise

            case CircuitState.CLOSED:
                try:
                    result = await operation(*args, **kwargs)
                    self._on_success()
                    return result
                except Exception:
                    self._on_failure()
                    raise

    def _on_success(self) -> None:
        self._failure_count = 0
        if self._state is CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = datetime.now(UTC)
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0


class CircuitBreakerOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""

    ...
