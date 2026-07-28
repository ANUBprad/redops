"""Tests for retry framework."""

from app.providers.runtime.policies.runtime_policies import BackoffStrategy, RetryPolicy
from app.providers.runtime.retry.retry_framework import (
    RetryContext,
    RetryEvaluator,
)


class TestRetryEvaluator:
    """Tests for RetryEvaluator."""

    def test_retries_disabled(self) -> None:
        policy = RetryPolicy(max_attempts=0)
        evaluator = RetryEvaluator(policy)
        decision = evaluator.evaluate(RetryContext(attempt=0))
        assert decision.should_retry is False
        assert "disabled" in decision.reason.lower()

    def test_max_attempts_reached(self) -> None:
        policy = RetryPolicy(max_attempts=3)
        evaluator = RetryEvaluator(policy)
        decision = evaluator.evaluate(RetryContext(attempt=3))
        assert decision.should_retry is False
        assert "max attempts" in decision.reason.lower()

    def test_budget_exhausted(self) -> None:
        policy = RetryPolicy(total_retry_budget_seconds=10.0)
        evaluator = RetryEvaluator(policy)
        decision = evaluator.evaluate(RetryContext(attempt=0, total_elapsed_seconds=15.0))
        assert decision.should_retry is False
        assert "budget" in decision.reason.lower()

    def test_non_retryable_error_code(self) -> None:
        policy = RetryPolicy(retryable_error_codes=("rate_limit", "timeout"))
        evaluator = RetryEvaluator(policy)
        decision = evaluator.evaluate(RetryContext(attempt=0, last_error_code="auth_error"))
        assert decision.should_retry is False
        assert "not retryable" in decision.reason.lower()

    def test_retryable_error_code(self) -> None:
        policy = RetryPolicy(retryable_error_codes=("rate_limit", "timeout"))
        evaluator = RetryEvaluator(policy)
        decision = evaluator.evaluate(RetryContext(attempt=0, last_error_code="rate_limit"))
        assert decision.should_retry is True
        assert decision.attempt == 1

    def test_fixed_backoff(self) -> None:
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.FIXED,
            base_delay_seconds=2.0,
            jitter=False,
        )
        evaluator = RetryEvaluator(policy)
        d1 = evaluator.evaluate(RetryContext(attempt=0))
        d2 = evaluator.evaluate(RetryContext(attempt=1))
        assert d1.delay_seconds == 2.0
        assert d2.delay_seconds == 2.0

    def test_exponential_backoff(self) -> None:
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay_seconds=1.0,
            jitter=False,
        )
        evaluator = RetryEvaluator(policy)
        d0 = evaluator.evaluate(RetryContext(attempt=0))
        d1 = evaluator.evaluate(RetryContext(attempt=1))
        d2 = evaluator.evaluate(RetryContext(attempt=2))
        assert d0.delay_seconds == 1.0
        assert d1.delay_seconds == 2.0
        assert d2.delay_seconds == 4.0

    def test_linear_backoff(self) -> None:
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.LINEAR,
            base_delay_seconds=1.0,
            jitter=False,
        )
        evaluator = RetryEvaluator(policy)
        d0 = evaluator.evaluate(RetryContext(attempt=0))
        d1 = evaluator.evaluate(RetryContext(attempt=1))
        assert d0.delay_seconds == 1.0
        assert d1.delay_seconds == 2.0

    def test_max_delay_cap(self) -> None:
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            base_delay_seconds=1.0,
            max_delay_seconds=5.0,
            jitter=False,
        )
        evaluator = RetryEvaluator(policy)
        decision = evaluator.evaluate(RetryContext(attempt=10))
        assert decision.delay_seconds <= 5.0

    def test_jitter_reduces_variance(self) -> None:
        policy = RetryPolicy(
            backoff_strategy=BackoffStrategy.FIXED,
            base_delay_seconds=10.0,
            jitter=True,
        )
        evaluator = RetryEvaluator(policy)
        delays = [evaluator.evaluate(RetryContext(attempt=0)).delay_seconds for _ in range(20)]
        assert any(d != 10.0 for d in delays)

    def test_successive_attempts_increment(self) -> None:
        policy = RetryPolicy(max_attempts=5)
        evaluator = RetryEvaluator(policy)
        for i in range(5):
            decision = evaluator.evaluate(RetryContext(attempt=i))
            assert decision.should_retry is True
            assert decision.attempt == i + 1

        decision = evaluator.evaluate(RetryContext(attempt=5))
        assert decision.should_retry is False
