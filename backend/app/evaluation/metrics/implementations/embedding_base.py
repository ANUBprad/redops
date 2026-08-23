"""Embedding-based metric base class."""

from __future__ import annotations

import math
import time
from typing import Any

from app.evaluation.metrics.domain import (
    Metric,
    MetricResult,
)


class EmbeddingMetric(Metric):
    """Base class for embedding-based metrics.

    Uses cosine similarity between embeddings to compute semantic
    similarity scores. Subclasses define what is being compared.
    """

    async def _get_embedding(self, text: str, input_data: Any) -> tuple[float, ...]:
        """Get embedding vector for text."""
        provider = input_data.metadata.get("_embedding_provider")
        model = input_data.metadata.get("_embedding_model", "text-embedding-3-small")

        if provider is None:
            msg = "Embedding metrics require '_embedding_provider' in metadata"
            raise RuntimeError(msg)

        from app.providers.models.options import EmbeddingOptions

        response = await provider.embed(
            [text],
            model=model,
            options=EmbeddingOptions(),
        )

        embedding = response.embedding
        if not isinstance(embedding, tuple):
            msg = "Embedding provider did not return a valid embedding vector"
            raise RuntimeError(msg)
        return embedding

    @staticmethod
    def _cosine_similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0

        dot_product = math.sumprod(a, b)
        norm_a = math.sqrt(math.sumprod(a, a))
        norm_b = math.sqrt(math.sumprod(b, b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _build_embedding_result(
        self,
        metric_name: str,
        score: float,
        start: float,
        reasoning: str = "",
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> MetricResult:
        """Build a MetricResult from an embedding score."""
        return MetricResult(
            metric_name=metric_name,
            score=score,
            normalized_score=max(0.0, min(1.0, score)),
            reasoning=reasoning,
            metadata=metadata or {},
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            error=error,
        )
