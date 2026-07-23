"""Retry and backoff policy abstractions.

Provides composable retry strategies with configurable backoff
algorithms. Used by provider adapters, database connections,
and any infrastructure that calls external services.
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = Any

BackoffFunc = Callable[[int], float]
"""Type alias for a function that computes delay in seconds given attempt number."""


class BackoffPolicy(ABC):
    """Abstract backoff policy for retry delays."""

    @abstractmethod
    def delay(self, attempt: int) -> float:
        """Return the delay in seconds for the given attempt number.

        Args:
            attempt: The current attempt number (1-based).

        Returns:
            Delay in seconds before the next retry.

        """
        ...


@dataclass
class ExponentialBackoff(BackoffPolicy):
    """Exponential backoff with optional jitter.

    delay = base_delay * (multiplier ** (attempt - 1)) + jitter
    """

    base_delay: float = 1.0
    multiplier: float = 2.0
    max_delay: float = 60.0
    jitter: bool = True

    def delay(self, attempt: int) -> float:
        d = self.base_delay * (self.multiplier ** (attempt - 1))
        d = min(d, self.max_delay)
        if self.jitter:
            d += random.uniform(0, d * 0.1)  # noqa: S311
        return d


@dataclass
class FixedBackoff(BackoffPolicy):
    """Constant delay between retries."""

    delay_seconds: float = 1.0

    def delay(self, attempt: int) -> float:  # noqa: ARG002
        return self.delay_seconds


@dataclass
class NoBackoff(BackoffPolicy):
    """No delay between retries (use with caution)."""

    def delay(self, attempt: int) -> float:  # noqa: ARG002
        return 0.0


@dataclass
class RetryPolicy:
    """Policy governing retry behavior for an operation.

    Usage:
        policy = RetryPolicy(max_retries=3, backoff=ExponentialBackoff())
        result = await with_retry(policy, my_async_func, arg1, arg2)
    """

    max_retries: int = 3
    backoff: BackoffPolicy = field(default_factory=ExponentialBackoff)
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


async def with_retry(
    policy: RetryPolicy,
    operation: Callable[..., Awaitable[T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute an async operation with retry logic.

    Args:
        policy: The retry policy governing this operation.
        operation: The async callable to retry.
        *args: Positional arguments passed to the operation.
        **kwargs: Keyword arguments passed to the operation.

    Returns:
        The result of the operation if it succeeds.

    Raises:
        The last exception encountered if all retries are exhausted.

    """
    last_exception: Exception | None = None

    for attempt in range(1, policy.max_retries + 1):
        try:
            return await operation(*args, **kwargs)
        except policy.retryable_exceptions as exc:
            last_exception = exc
            if attempt < policy.max_retries:
                delay = policy.backoff.delay(attempt)
                await asyncio.sleep(delay)

    if last_exception is not None:
        raise last_exception

    raise RuntimeError("Unexpected: retry loop completed without result or exception")
