"""Provider Runtime errors."""

from __future__ import annotations

from typing import Any

from app.kernel.exceptions.errors import InfrastructureError


class RuntimeBaseError(InfrastructureError):
    """Base error for all runtime errors."""

    def __init__(  # noqa: PLR0913
        self,
        message: str = "",
        *,
        error_code: str = "RUNTIME_ERROR",
        details: dict[str, Any] | None = None,
        retryable: bool = False,
        cause: BaseException | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Initialize runtime base error."""
        super().__init__(
            message,
            error_code=error_code,
            details=details,
            retryable=retryable,
            cause=cause,
            trace_id=trace_id,
        )


class CircuitBreakerOpenError(RuntimeBaseError):
    """Raised when circuit breaker is open."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        *,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Initialize circuit breaker open error."""
        super().__init__(
            message,
            error_code="CIRCUIT_BREAKER_OPEN",
            details=details,
            retryable=False,
            trace_id=trace_id,
        )


class RateLimitExceededError(RuntimeBaseError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after_seconds: float = 0.0,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Initialize rate limit exceeded error."""
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            message,
            error_code="RATE_LIMIT_EXCEEDED",
            details={**(details or {}), "retry_after_seconds": retry_after_seconds},
            retryable=True,
            trace_id=trace_id,
        )


class RetryExhaustedError(RuntimeBaseError):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        message: str = "Retry attempts exhausted",
        *,
        attempts: int = 0,
        last_error: BaseException | None = None,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Initialize retry exhausted error."""
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            message,
            error_code="RETRY_EXHAUSTED",
            details={**(details or {}), "attempts": attempts},
            retryable=False,
            cause=last_error,
            trace_id=trace_id,
        )


class ExecutionTimeoutError(RuntimeBaseError):
    """Raised when execution exceeds timeout."""

    def __init__(
        self,
        message: str = "Execution timed out",
        *,
        timeout_seconds: float = 0.0,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Initialize execution timeout error."""
        self.timeout_seconds = timeout_seconds
        super().__init__(
            message,
            error_code="EXECUTION_TIMEOUT",
            details={**(details or {}), "timeout_seconds": timeout_seconds},
            retryable=True,
            trace_id=trace_id,
        )


class BudgetExceededError(RuntimeBaseError):
    """Raised when execution budget is exceeded."""

    def __init__(  # noqa: PLR0913
        self,
        message: str = "Execution budget exceeded",
        *,
        budget_type: str = "",
        limit: float = 0.0,
        current: float = 0.0,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Initialize budget exceeded error."""
        self.budget_type = budget_type
        self.limit = limit
        self.current = current
        super().__init__(
            message,
            error_code="BUDGET_EXCEEDED",
            details={
                **(details or {}),
                "budget_type": budget_type,
                "limit": limit,
                "current": current,
            },
            retryable=False,
            trace_id=trace_id,
        )


class FallbackExhaustedError(RuntimeBaseError):
    """Raised when all fallback providers are exhausted."""

    def __init__(
        self,
        message: str = "All fallback providers exhausted",
        *,
        attempts: int = 0,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        """Initialize fallback exhausted error."""
        self.attempts = attempts
        super().__init__(
            message,
            error_code="FALLBACK_EXHAUSTED",
            details={**(details or {}), "attempts": attempts},
            retryable=False,
            trace_id=trace_id,
        )
