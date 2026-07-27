"""Rate limiting abstractions — policy objects only, no Redis."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.runtime.policies.runtime_policies import RateLimitPolicy


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Result of a rate limit check.

    Attributes:
        allowed: Whether the request is allowed.
        retry_after_seconds: Seconds to wait before retrying.
        current_usage: Current usage count.
        limit: Configured limit.
        remaining: Remaining allowance.

    """

    allowed: bool
    retry_after_seconds: float = 0.0
    current_usage: int = 0
    limit: int = 0
    remaining: int = 0


class SlidingWindowRateLimiter:
    """Sliding window rate limiter.

    In-memory implementation for policy evaluation.

    Usage:
        limiter = SlidingWindowRateLimiter(policy)
        result = limiter.check("provider_openai")
        if not result.allowed:
            raise RateLimitExceededError(...)

    """

    def __init__(self, policy: RateLimitPolicy) -> None:
        """Initialize rate limiter."""
        self._policy = policy
        self._request_timestamps: dict[str, deque[datetime]] = {}
        self._concurrent_counts: dict[str, int] = {}

    def check(self, key: str = "default") -> RateLimitResult:
        """Check if a request is allowed.

        Args:
            key: Rate limit key (e.g., provider name).

        Returns:
            RateLimitResult with allowance decision.

        """
        if self._policy.is_unlimited:
            return RateLimitResult(allowed=True, limit=0, remaining=0)

        now = datetime.now(UTC)

        if self._policy.concurrent_requests is not None:
            current = self._concurrent_counts.get(key, 0)
            if current >= self._policy.concurrent_requests:
                return RateLimitResult(
                    allowed=False,
                    current_usage=current,
                    limit=self._policy.concurrent_requests,
                    remaining=0,
                )

        if self._policy.requests_per_minute is not None:
            window_start = now - timedelta(minutes=1)
            timestamps = self._request_timestamps.setdefault(key, deque())

            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()

            current_count = len(timestamps)
            if current_count >= self._policy.requests_per_minute:
                oldest = timestamps[0]
                retry_after = (oldest + timedelta(minutes=1) - now).total_seconds()
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=max(0.0, retry_after),
                    current_usage=current_count,
                    limit=self._policy.requests_per_minute,
                    remaining=0,
                )

        return RateLimitResult(
            allowed=True,
            current_usage=self._request_timestamps.get(key, deque()).__len__(),
            limit=self._policy.requests_per_minute or 0,
            remaining=max(
                0,
                (self._policy.requests_per_minute or 0)
                - len(self._request_timestamps.get(key, deque())),
            ),
        )

    def record_request(self, key: str = "default") -> None:
        """Record that a request was made."""
        now = datetime.now(UTC)
        timestamps = self._request_timestamps.setdefault(key, deque())
        timestamps.append(now)

    def acquire_concurrent(self, key: str = "default") -> bool:
        """Acquire a concurrent slot."""
        current = self._concurrent_counts.get(key, 0)
        if (
            self._policy.concurrent_requests is not None
            and current >= self._policy.concurrent_requests
        ):
            return False
        self._concurrent_counts[key] = current + 1
        return True

    def release_concurrent(self, key: str = "default") -> None:
        """Release a concurrent slot."""
        current = self._concurrent_counts.get(key, 0)
        self._concurrent_counts[key] = max(0, current - 1)

    def reset(self, key: str | None = None) -> None:
        """Reset rate limiter state."""
        if key is None:
            self._request_timestamps.clear()
            self._concurrent_counts.clear()
        else:
            self._request_timestamps.pop(key, None)
            self._concurrent_counts.pop(key, None)
