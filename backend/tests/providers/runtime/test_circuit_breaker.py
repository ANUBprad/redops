"""Tests for circuit breaker."""

import time

from app.providers.runtime.circuit_breaker.runtime_circuit_breaker import (
    CircuitBreakerConfig,
    CircuitState,
    RuntimeCircuitBreaker,
)


class TestRuntimeCircuitBreaker:
    """Tests for RuntimeCircuitBreaker."""

    def test_starts_closed(self) -> None:
        cb = RuntimeCircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_threshold(self) -> None:
        cb = RuntimeCircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_half_open_after_recovery(self) -> None:
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout_seconds=0.1,
        )
        cb = RuntimeCircuitBreaker(config)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute() is True

    def test_closes_from_half_open(self) -> None:
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.05,
            success_threshold=2,
        )
        cb = RuntimeCircuitBreaker(config)
        cb.record_failure()
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_from_half_open_on_failure(self) -> None:
        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.05,
        )
        cb = RuntimeCircuitBreaker(config)
        cb.record_failure()
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_manual_reset(self) -> None:
        cb = RuntimeCircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_snapshot(self) -> None:
        cb = RuntimeCircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        cb.record_failure()
        snapshot = cb.snapshot()
        assert snapshot.failure_count == 1
        assert snapshot.state == CircuitState.CLOSED
        assert snapshot.total_rejected == 0

    def test_rejected_increment(self) -> None:
        cb = RuntimeCircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
        cb.record_failure()
        cb.can_execute()
        assert cb.snapshot().total_rejected == 1

    def test_consecutive_successes_reset(self) -> None:
        cb = RuntimeCircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._metrics.consecutive_successes == 1

    def test_failure_within_window_opens(self) -> None:
        """Two failures within window should still open the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            failure_window_seconds=60.0,
        )
        cb = RuntimeCircuitBreaker(config)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
