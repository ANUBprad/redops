"""Tests for timeout framework."""

from datetime import UTC, datetime, timedelta

from app.providers.runtime.policies.runtime_policies import TimeoutPolicy, TimeoutType
from app.providers.runtime.timeout.timeout_framework import (
    TimeoutEvaluator,
    TimeoutResult,
)


class TestTimeoutEvaluator:
    """Tests for TimeoutEvaluator."""

    def test_not_expired(self) -> None:
        policy = TimeoutPolicy(request_timeout_seconds=10.0)
        evaluator = TimeoutEvaluator(policy)
        start = datetime.now(UTC) - timedelta(seconds=5)
        result = evaluator.check(start, TimeoutType.SOFT)
        assert result.is_expired is False
        assert result.remaining_seconds > 0

    def test_expired(self) -> None:
        policy = TimeoutPolicy(request_timeout_seconds=5.0)
        evaluator = TimeoutEvaluator(policy)
        start = datetime.now(UTC) - timedelta(seconds=10)
        result = evaluator.check(start, TimeoutType.SOFT)
        assert result.is_expired is True
        assert result.remaining_seconds == 0.0

    def test_hard_timeout(self) -> None:
        policy = TimeoutPolicy(
            request_timeout_seconds=5.0,
            provider_timeout_seconds=30.0,
        )
        evaluator = TimeoutEvaluator(policy)
        start = datetime.now(UTC) - timedelta(seconds=10)
        soft_result = evaluator.check(start, TimeoutType.SOFT)
        hard_result = evaluator.check(start, TimeoutType.HARD)
        assert soft_result.is_expired is True
        assert hard_result.is_expired is False

    def test_effective_deadline(self) -> None:
        policy = TimeoutPolicy(request_timeout_seconds=10.0, provider_timeout_seconds=30.0)
        evaluator = TimeoutEvaluator(policy)
        start = datetime.now(UTC)
        deadline = evaluator.effective_deadline(start)
        assert deadline == start + timedelta(seconds=10.0)

    def test_immutability(self) -> None:
        result = TimeoutResult(
            is_expired=False,
            elapsed_seconds=5.0,
            remaining_seconds=5.0,
        )
        try:
            result.is_expired = True  # type: ignore[misc]
        except AttributeError:
            pass
        assert result.is_expired is False
