"""Tests for execution context."""

from app.providers.runtime.context.execution_context import (
    CancellationToken,
    ExecutionBudget,
    ExecutionContext,
)


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_default_values(self) -> None:
        ctx = ExecutionContext()
        assert ctx.provider_name == ""
        assert ctx.model_id == ""
        assert ctx.trace_id == ""

    def test_immutability(self) -> None:
        ctx = ExecutionContext(provider_name="openai")
        try:
            ctx.provider_name = "anthropic"  # type: ignore[misc]
        except AttributeError:
            pass
        assert ctx.provider_name == "openai"

    def test_with_retry(self) -> None:
        ctx = ExecutionContext(provider_name="openai", retry_count=0)
        ctx2 = ctx.with_retry(3)
        assert ctx2.retry_count == 3
        assert ctx2.provider_name == "openai"
        assert ctx.retry_count == 0

    def test_cancel_returns_new(self) -> None:
        ctx = ExecutionContext(provider_name="openai")
        cancelled = ctx.cancel("user requested")
        assert cancelled.is_cancelled is True
        assert cancelled.cancellation.reason == "user requested"
        assert ctx.is_cancelled is False

    def test_is_cancelled_property(self) -> None:
        ctx = ExecutionContext(
            provider_name="openai",
            cancellation=CancellationToken(is_cancelled=True, reason="test"),
        )
        assert ctx.is_cancelled is True


class TestCancellationToken:
    """Tests for CancellationToken."""

    def test_not_cancelled(self) -> None:
        token = CancellationToken()
        assert token.is_cancelled is False

    def test_cancel_returns_new(self) -> None:
        token = CancellationToken()
        cancelled = token.cancel("user requested")
        assert cancelled.is_cancelled is True
        assert token.is_cancelled is False

    def test_cancel_with_reason(self) -> None:
        token = CancellationToken()
        cancelled = token.cancel("user requested")
        assert cancelled.reason == "user requested"


class TestExecutionBudget:
    """Tests for ExecutionBudget."""

    def test_default_values(self) -> None:
        budget = ExecutionBudget()
        assert budget.max_cost_usd is None
        assert budget.max_tokens is None

    def test_is_unlimited(self) -> None:
        budget = ExecutionBudget()
        assert budget.is_unlimited is True

    def test_not_unlimited(self) -> None:
        budget = ExecutionBudget(max_cost_usd=1.0)
        assert budget.is_unlimited is False

    def test_immutability(self) -> None:
        budget = ExecutionBudget(max_cost_usd=1.0)
        try:
            budget.max_cost_usd = 2.0  # type: ignore[misc]
        except AttributeError:
            pass
        assert budget.max_cost_usd == 1.0
