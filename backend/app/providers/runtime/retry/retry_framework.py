"""Retry framework — pure retry decisions and delay calculation."""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.providers.runtime.policies.runtime_policies import BackoffStrategy, RetryPolicy


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Immutable result of a retry decision.

    Attributes:
        should_retry: Whether to retry.
        delay_seconds: Delay before next attempt.
        attempt: Current attempt number.
        reason: Human-readable reason.

    """

    should_retry: bool
    delay_seconds: float = 0.0
    attempt: int = 0
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RetryContext:
    """Immutable context for retry decisions.

    Attributes:
        attempt: Current attempt number (0-indexed).
        total_elapsed_seconds: Total time spent in retries.
        last_error_code: Error code from last failure.
        last_error_message: Error message from last failure.
        consecutive_failures: Number of consecutive failures.

    """

    attempt: int = 0
    total_elapsed_seconds: float = 0.0
    last_error_code: str = ""
    last_error_message: str = ""
    consecutive_failures: int = 0


class RetryEvaluator:
    """Evaluates whether a retry should be attempted.

    Pure logic, no side effects.

    Usage:
        evaluator = RetryEvaluator(policy)
        decision = evaluator.evaluate(context)
        if decision.should_retry:
            await asyncio.sleep(decision.delay_seconds)

    """

    def __init__(self, policy: RetryPolicy) -> None:
        """Initialize with retry policy."""
        self._policy = policy

    def evaluate(self, ctx: RetryContext) -> RetryDecision:
        """Evaluate whether to retry based on context.

        Args:
            ctx: Current retry context.

        Returns:
            RetryDecision with retry guidance.

        """
        if not self._policy.is_enabled:
            return RetryDecision(
                should_retry=False,
                attempt=ctx.attempt,
                reason="Retries disabled",
            )

        if ctx.attempt >= self._policy.max_attempts:
            return RetryDecision(
                should_retry=False,
                attempt=ctx.attempt,
                reason=f"Max attempts ({self._policy.max_attempts}) reached",
            )

        if ctx.total_elapsed_seconds >= self._policy.total_retry_budget_seconds:
            return RetryDecision(
                should_retry=False,
                attempt=ctx.attempt,
                reason="Retry budget exhausted",
            )

        if (
            self._policy.retryable_error_codes
            and ctx.last_error_code
            and ctx.last_error_code not in self._policy.retryable_error_codes
        ):
            return RetryDecision(
                should_retry=False,
                attempt=ctx.attempt,
                reason=f"Error code '{ctx.last_error_code}' not retryable",
            )

        delay = self._calculate_delay(ctx.attempt)

        return RetryDecision(
            should_retry=True,
            delay_seconds=delay,
            attempt=ctx.attempt + 1,
            reason="Retry eligible",
        )

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt with optional jitter."""
        if self._policy.backoff_strategy == BackoffStrategy.FIXED:
            delay = self._policy.base_delay_seconds
        elif self._policy.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self._policy.base_delay_seconds * (attempt + 1)
        else:
            delay = self._policy.base_delay_seconds * (2.0**attempt)

        delay = min(delay, self._policy.max_delay_seconds)

        if self._policy.jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
            delay = max(0.0, delay)

        return delay
