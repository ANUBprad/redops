"""Tests for fallback chain."""

import pytest

from app.providers.runtime.fallback.fallback_chain import (
    FallbackChain,
    FallbackDecision,
    FallbackEntry,
    FallbackState,
    FallbackStrategy,
)


class TestFallbackChain:
    """Tests for FallbackChain."""

    def test_empty_chain_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            FallbackChain([])

    def test_single_entry(self) -> None:
        chain = FallbackChain([FallbackEntry(provider_name="openai", model_id="gpt-4")])
        decision = chain.next()
        assert decision is not None
        assert decision.provider_name == "openai"
        assert decision.is_final is True

    def test_round_robin_advances(self) -> None:
        entries = [
            FallbackEntry(provider_name="openai", model_id="gpt-4", priority=0),
            FallbackEntry(provider_name="anthropic", model_id="claude", priority=1),
        ]
        chain = FallbackChain(entries)
        d1 = chain.next()
        assert d1 is not None and d1.provider_name == "openai"

        chain.record_failure()
        d2 = chain.next()
        assert d2 is not None and d2.provider_name == "anthropic"

    def test_record_success_resets(self) -> None:
        entries = [
            FallbackEntry(provider_name="openai", model_id="gpt-4"),
            FallbackEntry(provider_name="anthropic", model_id="claude"),
        ]
        chain = FallbackChain(entries)
        chain.next()
        chain.record_success()
        decision = chain.next()
        assert decision is not None and decision.provider_name == "openai"

    def test_exhausted_chain(self) -> None:
        chain = FallbackChain(
            [FallbackEntry(provider_name="openai", model_id="gpt-4", max_retries=1)]
        )
        chain.next()
        chain.record_failure()
        assert chain.is_exhausted is True
        assert chain.next() is None

    def test_max_retries_per_entry(self) -> None:
        entries = [
            FallbackEntry(provider_name="openai", model_id="gpt-4", max_retries=2),
            FallbackEntry(provider_name="anthropic", model_id="claude", max_retries=1),
        ]
        chain = FallbackChain(entries)
        chain.next()
        chain.record_failure()
        chain.next()
        chain.record_failure()
        assert chain._state.current_index == 1

    def test_reset(self) -> None:
        entries = [
            FallbackEntry(provider_name="openai", model_id="gpt-4"),
            FallbackEntry(provider_name="anthropic", model_id="claude"),
        ]
        chain = FallbackChain(entries)
        chain.next()
        chain.record_failure()
        chain.reset()
        assert chain._state.current_index == 0

    def test_decision_immutability(self) -> None:
        decision = FallbackDecision(
            provider_name="openai", model_id="gpt-4", index=0, is_final=False, attempt_count=0,
        )
        try:
            decision.provider_name = "anthropic"  # type: ignore[misc]
        except AttributeError:
            pass
        assert decision.provider_name == "openai"
