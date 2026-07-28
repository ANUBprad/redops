"""Tests for runtime policies."""

from app.providers.runtime.policies.runtime_policies import (
    BackoffStrategy,
    CachingPolicy,
    ExecutionPolicy,
    FallbackPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TelemetryPolicy,
    TimeoutPolicy,
)


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_default_values(self) -> None:
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.base_delay_seconds == 1.0
        assert policy.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert policy.jitter is True

    def test_is_enabled(self) -> None:
        assert RetryPolicy(max_attempts=3).is_enabled is True
        assert RetryPolicy(max_attempts=0).is_enabled is False

    def test_immutability(self) -> None:
        policy = RetryPolicy(max_attempts=5)
        try:
            policy.max_attempts = 10  # type: ignore[misc]
        except AttributeError:
            pass
        assert policy.max_attempts == 5

    def test_delay_for_attempt(self) -> None:
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay_seconds=1.0,
            jitter=False,
        )
        assert policy.delay_for_attempt(0) == 1.0
        assert policy.delay_for_attempt(1) == 2.0
        assert policy.delay_for_attempt(2) == 4.0


class TestTimeoutPolicy:
    """Tests for TimeoutPolicy."""

    def test_default_values(self) -> None:
        policy = TimeoutPolicy()
        assert policy.request_timeout_seconds == 60.0
        assert policy.provider_timeout_seconds == 300.0

    def test_effective_timeout(self) -> None:
        policy = TimeoutPolicy(request_timeout_seconds=10, provider_timeout_seconds=30)
        assert policy.effective_timeout == 10


class TestFallbackPolicy:
    """Tests for FallbackPolicy."""

    def test_default_values(self) -> None:
        policy = FallbackPolicy()
        assert policy.enabled is True
        assert policy.max_fallback_attempts == 3


class TestRateLimitPolicy:
    """Tests for RateLimitPolicy."""

    def test_unlimited(self) -> None:
        policy = RateLimitPolicy()
        assert policy.is_unlimited is True

    def test_limited(self) -> None:
        policy = RateLimitPolicy(requests_per_minute=60)
        assert policy.is_unlimited is False


class TestCachingPolicy:
    """Tests for CachingPolicy."""

    def test_default_values(self) -> None:
        policy = CachingPolicy()
        assert policy.enabled is False
        assert policy.ttl_seconds == 300.0


class TestTelemetryPolicy:
    """Tests for TelemetryPolicy."""

    def test_default_values(self) -> None:
        policy = TelemetryPolicy()
        assert policy.enabled is True
        assert policy.capture_latency is True


class TestExecutionPolicy:
    """Tests for ExecutionPolicy composite."""

    def test_default_composite(self) -> None:
        policy = ExecutionPolicy()
        assert policy.retry.max_attempts == 3
        assert policy.timeout.request_timeout_seconds == 60.0
        assert policy.fallback.enabled is True
