"""Tests for runtime errors."""

from app.providers.runtime.errors.runtime_errors import (
    BudgetExceededError,
    CircuitBreakerOpenError,
    ExecutionTimeoutError,
    FallbackExhaustedError,
    RateLimitExceededError,
    RetryExhaustedError,
    RuntimeBaseError,
)


class TestRuntimeErrors:
    """Tests for runtime error hierarchy."""

    def test_base_error(self) -> None:
        err = RuntimeBaseError(message="test error", error_code="TEST_001")
        assert str(err) == "test error"
        assert err.error_code == "TEST_001"
        assert isinstance(err, Exception)

    def test_circuit_breaker_error(self) -> None:
        err = CircuitBreakerOpenError(message="openai circuit open")
        assert "openai" in str(err)

    def test_rate_limit_error(self) -> None:
        err = RateLimitExceededError(retry_after_seconds=30.0)
        assert err.retry_after_seconds == 30.0

    def test_retry_exhausted_error(self) -> None:
        err = RetryExhaustedError(attempts=3)
        assert err.attempts == 3

    def test_timeout_error(self) -> None:
        err = ExecutionTimeoutError(timeout_seconds=10.0)
        assert err.timeout_seconds == 10.0

    def test_budget_exceeded_error(self) -> None:
        err = BudgetExceededError(budget_type="cost", limit=5.0, current=6.5)
        assert err.limit == 5.0
        assert err.current == 6.5
        assert err.budget_type == "cost"

    def test_fallback_exhausted_error(self) -> None:
        err = FallbackExhaustedError(attempts=2)
        assert err.attempts == 2

    def test_all_inherit_from_base(self) -> None:
        errors = [
            CircuitBreakerOpenError(),
            RateLimitExceededError(),
            RetryExhaustedError(),
            ExecutionTimeoutError(),
            BudgetExceededError(),
            FallbackExhaustedError(),
        ]
        for err in errors:
            assert isinstance(err, RuntimeBaseError)
            assert isinstance(err, Exception)
