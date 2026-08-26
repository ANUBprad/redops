"""Tests for cost and latency accounting determinism."""

from __future__ import annotations

from app.evaluation.reliability.accounting import (
    ProviderCallCounter,
    ProviderCallRecord,
)


class TestCostAccounting:
    def test_zero_cost_initial(self) -> None:
        counter = ProviderCallCounter()
        assert counter.total_cost_usd == 0.0

    def test_target_cost_accumulates(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="target", cost_usd=0.01)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="target", cost_usd=0.02)
        )
        assert abs(counter.target_cost_usd - 0.03) < 1e-9

    def test_judge_cost_accumulates(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="judge", cost_usd=0.005)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="judge", cost_usd=0.005)
        )
        assert abs(counter.judge_cost_usd - 0.01) < 1e-9

    def test_embedding_cost_accumulates(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="embedding", cost_usd=0.001)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="embedding", cost_usd=0.001)
        )
        assert abs(counter.embedding_cost_usd - 0.002) < 1e-9

    def test_total_cost_sums_all_types(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="target", cost_usd=0.01)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="judge", cost_usd=0.02)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="embedding", cost_usd=0.003)
        )
        assert abs(counter.total_cost_usd - 0.033) < 1e-9


class TestLatencyAccounting:
    def test_zero_latency_initial(self) -> None:
        counter = ProviderCallCounter()
        assert counter.total_latency_ms == 0

    def test_target_latency_accumulates(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="target", latency_ms=100)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="target", latency_ms=200)
        )
        assert counter.target_latency_ms == 300

    def test_judge_latency_accumulates(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="judge", latency_ms=150)
        )
        assert counter.judge_latency_ms == 150

    def test_embedding_latency_accumulates(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="embedding", latency_ms=30)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="embedding", latency_ms=40)
        )
        assert counter.embedding_latency_ms == 70

    def test_total_latency_sums_all_types(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="target", latency_ms=100)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="judge", latency_ms=150)
        )
        counter.record(
            ProviderCallRecord(provider="o", model="m", call_type="embedding", latency_ms=30)
        )
        assert counter.total_latency_ms == 280


class TestTokenAccounting:
    def test_zero_tokens_initial(self) -> None:
        counter = ProviderCallCounter()
        assert counter.total_tokens_input == 0
        assert counter.total_tokens_output == 0

    def test_target_tokens(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="o", model="m", call_type="target", tokens_input=100, tokens_output=50
            )
        )
        assert counter.target_tokens_input == 100
        assert counter.target_tokens_output == 50

    def test_judge_tokens(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="o", model="m", call_type="judge", tokens_input=200, tokens_output=100
            )
        )
        assert counter.judge_tokens_input == 200
        assert counter.judge_tokens_output == 100

    def test_embedding_tokens(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="o", model="m", call_type="embedding", tokens_input=50, tokens_output=0
            )
        )
        assert counter.embedding_tokens_input == 50
        assert counter.embedding_tokens_output == 0

    def test_total_tokens_sums_all_types(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="o", model="m", call_type="target", tokens_input=100, tokens_output=50
            )
        )
        counter.record(
            ProviderCallRecord(
                provider="o", model="m", call_type="judge", tokens_input=200, tokens_output=100
            )
        )
        counter.record(
            ProviderCallRecord(
                provider="o", model="m", call_type="embedding", tokens_input=50, tokens_output=0
            )
        )
        assert counter.total_tokens_input == 350
        assert counter.total_tokens_output == 150
