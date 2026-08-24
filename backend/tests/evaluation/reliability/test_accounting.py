"""Tests for provider call accounting."""

from __future__ import annotations

from app.evaluation.reliability.accounting import (
    ProviderCallCounter,
    ProviderCallRecord,
)


class TestProviderCallCounter:
    def test_initial_state(self) -> None:
        counter = ProviderCallCounter()
        assert counter.total_calls == 0
        assert counter.target_calls == 0
        assert counter.judge_calls == 0
        assert counter.embedding_calls == 0
        assert counter.total_cost_usd == 0.0
        assert counter.total_tokens_input == 0
        assert counter.total_tokens_output == 0
        assert counter.total_latency_ms == 0
        assert counter.errors == 0

    def test_record_target_call(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="openai",
                model="gpt-4",
                call_type="target",
                tokens_input=100,
                tokens_output=50,
                cost_usd=0.01,
                latency_ms=200,
            )
        )
        assert counter.target_calls == 1
        assert counter.total_calls == 1
        assert counter.target_tokens_input == 100
        assert counter.target_tokens_output == 50
        assert counter.target_cost_usd == 0.01
        assert counter.target_latency_ms == 200
        assert counter.errors == 0

    def test_record_judge_call(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="openai",
                model="gpt-4",
                call_type="judge",
                tokens_input=200,
                tokens_output=100,
                cost_usd=0.02,
                latency_ms=300,
            )
        )
        assert counter.judge_calls == 1
        assert counter.judge_tokens_input == 200
        assert counter.judge_cost_usd == 0.02
        assert counter.judge_latency_ms == 300

    def test_record_embedding_call(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="openai",
                model="text-embedding-3-small",
                call_type="embedding",
                tokens_input=50,
                tokens_output=0,
                cost_usd=0.001,
                latency_ms=50,
            )
        )
        assert counter.embedding_calls == 1
        assert counter.embedding_tokens_input == 50
        assert counter.embedding_cost_usd == 0.001
        assert counter.embedding_latency_ms == 50

    def test_multiple_calls_accumulate(self) -> None:
        counter = ProviderCallCounter()
        for _ in range(3):
            counter.record(ProviderCallRecord(provider="openai", model="gpt-4", call_type="target"))
        assert counter.target_calls == 3
        assert counter.total_calls == 3

    def test_error_counted(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="openai",
                model="gpt-4",
                call_type="target",
                error="timeout",
            )
        )
        assert counter.errors == 1

    def test_total_cost_sums_types(self) -> None:
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

    def test_embedding_reuse_protection(self) -> None:
        """Verify that recording 4 embedding calls (not 8) is correctly tracked."""
        counter = ProviderCallCounter()
        for _ in range(4):
            counter.record(
                ProviderCallRecord(
                    provider="openai",
                    model="text-embedding-3-small",
                    call_type="embedding",
                    tokens_input=100,
                )
            )
        assert counter.embedding_calls == 4
        assert counter.total_calls == 4

    def test_to_summary(self) -> None:
        counter = ProviderCallCounter()
        counter.record(
            ProviderCallRecord(
                provider="openai",
                model="gpt-4",
                call_type="target",
                tokens_input=10,
                tokens_output=5,
                cost_usd=0.01,
                latency_ms=100,
            )
        )
        summary = counter.to_summary()
        assert summary["target_calls"] == 1
        assert summary["total_cost_usd"] == 0.01
        assert summary["target_latency_ms"] == 100
