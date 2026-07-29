"""Timeout framework — pure timeout policy enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.providers.runtime.policies.runtime_policies import TimeoutPolicy, TimeoutType


@dataclass(frozen=True, slots=True)
class TimeoutResult:
    """Result of a timeout check.

    Attributes:
        is_expired: Whether the timeout has been exceeded.
        elapsed_seconds: Time elapsed since start.
        remaining_seconds: Time remaining before timeout.
        timeout_type: Type of timeout that triggered.

    """

    is_expired: bool
    elapsed_seconds: float = 0.0
    remaining_seconds: float = 0.0
    timeout_type: TimeoutType = TimeoutType.SOFT


class TimeoutEvaluator:
    """Evaluates timeout conditions.

    Pure logic, no side effects.

    Usage:
        evaluator = TimeoutEvaluator(policy)
        result = evaluator.check(start_time, TimeoutType.SOFT)
        if result.is_expired:
            raise ExecutionTimeoutError(...)

    """

    def __init__(self, policy: TimeoutPolicy) -> None:
        """Initialize with timeout policy."""
        self._policy = policy

    def check(
        self,
        start_time: datetime,
        timeout_type: TimeoutType = TimeoutType.SOFT,
    ) -> TimeoutResult:
        """Check if timeout has been exceeded.

        Args:
            start_time: When execution started.
            timeout_type: Type of timeout to check.

        Returns:
            TimeoutResult with expiration status.

        """
        now = datetime.now(UTC)
        elapsed = (now - start_time).total_seconds()

        if timeout_type == TimeoutType.HARD:
            limit = self._policy.provider_timeout_seconds
        else:
            limit = self._policy.request_timeout_seconds

        remaining = max(0.0, limit - elapsed)

        return TimeoutResult(
            is_expired=elapsed > limit,
            elapsed_seconds=elapsed,
            remaining_seconds=remaining,
            timeout_type=timeout_type,
        )

    def effective_deadline(self, start_time: datetime) -> datetime:
        """Calculate the effective deadline from start time."""
        return start_time + timedelta(seconds=self._policy.effective_timeout)
