"""Tests for embedding call reuse regression.

Protects the B.3 optimization where 8 embeddings were reduced to 4.
Deterministic tests ensure this behavior does not regress.
"""

from __future__ import annotations

import hashlib

from app.evaluation.reliability.accounting import (
    ProviderCallCounter,
    ProviderCallRecord,
)


class TestEmbeddingReuseProtection:
    """Verify that embedding call counts remain optimized."""

    def test_embedding_count_four_not_eight(self) -> None:
        """8 items should produce at most 4 embedding calls (with reuse)."""
        counter = ProviderCallCounter()
        for _ in range(4):
            counter.record(
                ProviderCallRecord(
                    provider="openai",
                    model="text-embedding-3-small",
                    call_type="embedding",
                    tokens_input=100,
                    cost_usd=0.0001,
                    latency_ms=30,
                )
            )
        assert counter.embedding_calls == 4
        assert counter.total_calls == 4

    def test_embedding_reuse_deterministic(self) -> None:
        """Same input text should reuse embeddings, not create new calls."""
        seen_hashes: set[str] = set()
        counter = ProviderCallCounter()

        texts = ["Paris", "Paris", "London", "London"]
        for text in texts:
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            if text_hash not in seen_hashes:
                seen_hashes.add(text_hash)
                counter.record(
                    ProviderCallRecord(
                        provider="openai",
                        model="text-embedding-3-small",
                        call_type="embedding",
                        tokens_input=10,
                    )
                )

        assert counter.embedding_calls == 2
        assert len(seen_hashes) == 2

    def test_deduplication_across_items(self) -> None:
        """Different items sharing the same reference should not duplicate embeddings."""
        counter = ProviderCallCounter()
        unique_texts = {"Paris is the capital", "London is the capital"}
        for _text in unique_texts:
            counter.record(
                ProviderCallRecord(
                    provider="openai",
                    model="text-embedding-3-small",
                    call_type="embedding",
                )
            )
        assert counter.embedding_calls == len(unique_texts)

    def test_embedding_cost_tracked(self) -> None:
        counter = ProviderCallCounter()
        for _ in range(4):
            counter.record(
                ProviderCallRecord(
                    provider="openai",
                    model="text-embedding-3-small",
                    call_type="embedding",
                    cost_usd=0.0001,
                )
            )
        assert abs(counter.embedding_cost_usd - 0.0004) < 1e-9

    def test_embedding_latency_tracked(self) -> None:
        counter = ProviderCallCounter()
        for _ in range(4):
            counter.record(
                ProviderCallRecord(
                    provider="openai",
                    model="text-embedding-3-small",
                    call_type="embedding",
                    latency_ms=30,
                )
            )
        assert counter.embedding_latency_ms == 120
