"""Tests for runtime telemetry models."""

from datetime import UTC, datetime

from app.providers.runtime.telemetry.runtime_telemetry import (
    CompletionStatus,
    CostEstimate,
    FailureCategory,
    LatencyMetrics,
    RuntimeTelemetry,
    TokenUsage,
)


class TestTokenUsage:
    """Tests for TokenUsage."""

    def test_default_values(self) -> None:
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.total_tokens == 0

    def test_has_usage_true(self) -> None:
        usage = TokenUsage(total_tokens=100)
        assert usage.has_usage is True

    def test_has_usage_false(self) -> None:
        usage = TokenUsage()
        assert usage.has_usage is False

    def test_immutability(self) -> None:
        usage = TokenUsage(total_tokens=50)
        try:
            usage.total_tokens = 100  # type: ignore[misc]
        except AttributeError:
            pass
        assert usage.total_tokens == 50


class TestCostEstimate:
    """Tests for CostEstimate."""

    def test_default_values(self) -> None:
        cost = CostEstimate()
        assert cost.input_cost_usd == 0.0
        assert cost.output_cost_usd == 0.0
        assert cost.total_cost_usd == 0.0
        assert cost.currency == "USD"

    def test_custom_values(self) -> None:
        cost = CostEstimate(input_cost_usd=0.01, output_cost_usd=0.02, total_cost_usd=0.03)
        assert cost.total_cost_usd == 0.03


class TestLatencyMetrics:
    """Tests for LatencyMetrics."""

    def test_default_values(self) -> None:
        latency = LatencyMetrics()
        assert latency.total_ms == 0.0
        assert latency.provider_ms == 0.0

    def test_overhead_calculation(self) -> None:
        latency = LatencyMetrics(total_ms=100.0, provider_ms=80.0)
        assert latency.overhead_ms == 20.0

    def test_overhead_no_negative(self) -> None:
        latency = LatencyMetrics(total_ms=50.0, provider_ms=80.0)
        assert latency.overhead_ms == 0.0


class TestRuntimeTelemetry:
    """Tests for RuntimeTelemetry."""

    def test_default_values(self) -> None:
        telemetry = RuntimeTelemetry()
        assert telemetry.request_id == ""
        assert telemetry.status == CompletionStatus.SUCCESS
        assert telemetry.is_success is True
        assert telemetry.is_failure is False

    def test_failure_status(self) -> None:
        telemetry = RuntimeTelemetry(status=CompletionStatus.FAILED)
        assert telemetry.is_success is False
        assert telemetry.is_failure is True

    def test_immutability(self) -> None:
        telemetry = RuntimeTelemetry(request_id="req-1")
        try:
            telemetry.request_id = "req-2"  # type: ignore[misc]
        except AttributeError:
            pass
        assert telemetry.request_id == "req-1"

    def test_with_all_fields(self) -> None:
        telemetry = RuntimeTelemetry(
            request_id="req-1",
            provider_name="openai",
            model_id="gpt-4",
            status=CompletionStatus.SUCCESS,
            latency=LatencyMetrics(total_ms=150.0),
            tokens=TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            cost=CostEstimate(total_cost_usd=0.001),
            retry_count=2,
            fallback_count=1,
            circuit_breaker_state="closed",
            streaming_duration_ms=120.0,
        )
        assert telemetry.retry_count == 2
        assert telemetry.fallback_count == 1
        assert telemetry.tokens.total_tokens == 30
        assert telemetry.cost.total_cost_usd == 0.001
