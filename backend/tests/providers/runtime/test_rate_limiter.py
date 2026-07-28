"""Tests for rate limiter."""

from app.providers.runtime.policies.runtime_policies import RateLimitPolicy
from app.providers.runtime.rate_limit.rate_limiter import (
    RateLimitResult,
    SlidingWindowRateLimiter,
)


class TestSlidingWindowRateLimiter:
    """Tests for SlidingWindowRateLimiter."""

    def test_unlimited_policy(self) -> None:
        policy = RateLimitPolicy()
        limiter = SlidingWindowRateLimiter(policy)
        result = limiter.check()
        assert result.allowed is True

    def test_within_limit(self) -> None:
        policy = RateLimitPolicy(requests_per_minute=10)
        limiter = SlidingWindowRateLimiter(policy)
        for _ in range(5):
            limiter.record_request()
        result = limiter.check()
        assert result.allowed is True
        assert result.remaining == 5

    def test_at_limit(self) -> None:
        policy = RateLimitPolicy(requests_per_minute=3)
        limiter = SlidingWindowRateLimiter(policy)
        for _ in range(3):
            limiter.record_request()
        result = limiter.check()
        assert result.allowed is False
        assert result.retry_after_seconds > 0

    def test_concurrent_limit(self) -> None:
        policy = RateLimitPolicy(concurrent_requests=2)
        limiter = SlidingWindowRateLimiter(policy)
        assert limiter.acquire_concurrent() is True
        assert limiter.acquire_concurrent() is True
        assert limiter.acquire_concurrent() is False

    def test_concurrent_release(self) -> None:
        policy = RateLimitPolicy(concurrent_requests=1)
        limiter = SlidingWindowRateLimiter(policy)
        limiter.acquire_concurrent()
        limiter.release_concurrent()
        assert limiter.acquire_concurrent() is True

    def test_reset(self) -> None:
        policy = RateLimitPolicy(requests_per_minute=2)
        limiter = SlidingWindowRateLimiter(policy)
        limiter.record_request()
        limiter.record_request()
        limiter.reset()
        result = limiter.check()
        assert result.allowed is True

    def test_reset_specific_key(self) -> None:
        policy = RateLimitPolicy(requests_per_minute=1)
        limiter = SlidingWindowRateLimiter(policy)
        limiter.record_request("key1")
        limiter.record_request("key2")
        limiter.reset("key1")
        assert limiter.check("key1").allowed is True
        assert limiter.check("key2").allowed is False

    def test_result_immutability(self) -> None:
        result = RateLimitResult(allowed=True, limit=10, remaining=5)
        try:
            result.allowed = False  # type: ignore[misc]
        except AttributeError:
            pass
        assert result.allowed is True
