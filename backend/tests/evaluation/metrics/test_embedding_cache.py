"""Measure embedding reuse across metrics within a single item boundary.

Baseline: every embedding metric fetches its own vectors, so the same
response text gets embedded once per metric. With a per-MetricInput
cache the duplicate round-trips disappear. This suite measures both.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.evaluation.metrics.domain import MetricInput
from app.evaluation.metrics.implementations.answer_relevance_metric import (
    AnswerRelevanceMetric,
)
from app.evaluation.metrics.implementations.context_relevance_metric import (
    ContextRelevanceMetric,
)
from app.evaluation.metrics.implementations.semantic_similarity_metric import (
    SemanticSimilarityMetric,
)
from app.providers.models.responses import EmbeddingResponse, Usage

PROMPT = "What is the capital of France?"
RESPONSE = "Paris is the capital of France."
REFERENCE = "Paris is the capital of France"
CONTEXT = "France is a country in Europe. Its capital is Paris."


class CountingEmbeddingProvider:
    """Embedding provider that records every batched request."""

    def __init__(self, latency_s: float = 0.001) -> None:
        self._latency_s = latency_s
        self.calls: list[list[str]] = []

    @property
    def provider_name(self) -> str:
        return "counting-embeddings"

    async def embed(
        self,
        texts: list[str],
        *,
        model: str = "",
        options: Any = None,
    ) -> EmbeddingResponse:
        import asyncio

        await asyncio.sleep(self._latency_s)
        self.calls.append(list(texts))
        vector = (1.0, 0.0, 0.0)
        return EmbeddingResponse(
            embedding=vector,
            dimensions=len(vector),
            model=model or "embed-test",
            provider=self.provider_name,
            usage=Usage(input_tokens=len(texts), output_tokens=0, total_tokens=len(texts)),
        )


EMBEDDING_METRICS = [
    SemanticSimilarityMetric(),
    AnswerRelevanceMetric(),
    ContextRelevanceMetric(),
]


def _item_input(metadata: dict[str, Any]) -> MetricInput:
    return MetricInput(
        prompt=PROMPT,
        response=RESPONSE,
        reference=REFERENCE,
        context=CONTEXT,
        metadata=metadata,
    )


def _texts_embedded(provider: CountingEmbeddingProvider) -> int:
    return sum(len(batch) for batch in provider.calls)


@pytest.mark.asyncio
async def test_baseline_embeds_duplicate_texts_without_cache() -> None:
    """Without a cache every metric pays for its own round-trips."""
    provider = CountingEmbeddingProvider()
    for metric in EMBEDDING_METRICS:
        await metric.evaluate(_item_input({"_embedding_provider": provider}))

    total = _texts_embedded(provider)
    unique = len({t for batch in provider.calls for t in batch})
    assert total == 6  # two round-trips per metric (3 metrics)
    assert unique == 4  # prompt, response, reference, context


@pytest.mark.asyncio
async def test_shared_item_cache_embeds_each_text_once() -> None:
    """A per-item cache cuts round-trips to the number of unique texts."""
    provider = CountingEmbeddingProvider()
    metadata: dict[str, Any] = {"_embedding_provider": provider}
    for metric in EMBEDDING_METRICS:
        await metric.evaluate(_item_input(metadata))

    total = _texts_embedded(provider)
    assert total == 4  # each unique text embedded exactly once


@pytest.mark.asyncio
async def test_cached_scores_match_uncached_scores() -> None:
    """Caching must not change any produced score."""
    uncached_provider = CountingEmbeddingProvider()
    cached_provider = CountingEmbeddingProvider()

    uncached: dict[str, float] = {}
    for metric in EMBEDDING_METRICS:
        result = await metric.evaluate(_item_input({"_embedding_provider": uncached_provider}))
        uncached[metric.definition().name] = result.normalized_score

    cached_metadata: dict[str, Any] = {"_embedding_provider": cached_provider}
    for metric in EMBEDDING_METRICS:
        result = await metric.evaluate(_item_input(cached_metadata))
        assert result.normalized_score == uncached[metric.definition().name]

    assert _texts_embedded(cached_provider) < _texts_embedded(uncached_provider)


@pytest.mark.asyncio
async def test_cache_reduces_wall_clock_latency() -> None:
    """With realistic per-call latency the cache saves measurable time."""
    import time

    latency = 0.02  # 20 ms simulated network round-trip

    async def run(shared_metadata: bool) -> tuple[float, int]:
        provider = CountingEmbeddingProvider(latency_s=latency)
        shared: dict[str, Any] = {"_embedding_provider": provider}
        start = time.perf_counter()
        for metric in EMBEDDING_METRICS:
            metadata = shared if shared_metadata else {"_embedding_provider": provider}
            await metric.evaluate(_item_input(metadata))
        return time.perf_counter() - start, _texts_embedded(provider)

    baseline_elapsed, baseline_calls = await run(shared_metadata=False)
    cached_elapsed, cached_calls = await run(shared_metadata=True)

    assert baseline_calls == 6  # isolated inputs: every metric pays again
    assert cached_calls == 4  # shared item boundary: unique texts only
    assert cached_elapsed < baseline_elapsed * 0.8
