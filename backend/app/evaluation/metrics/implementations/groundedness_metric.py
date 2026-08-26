"""Groundedness metric — embedding-based evaluation."""

from __future__ import annotations

import time

from app.evaluation.metrics.domain import (
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.implementations.embedding_base import EmbeddingMetric


class GroundednessMetric(EmbeddingMetric):
    """Evaluates whether the response is supported by the context using embeddings."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="groundedness",
            display_name="Groundedness",
            description="Measures if the response is supported by the context",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            requires_context=True,
            tags=("quality", "faithfulness", "rag", "embedding"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        if not input_data.context:
            return "Groundedness requires context to evaluate against"
        return None

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        if not input_data.response:
            return self._build_embedding_result(
                "groundedness",
                0.0,
                start,
                reasoning="Missing response",
                error="Missing response",
            )

        validation_error = self.validate_input(input_data)
        if validation_error:
            return self._build_embedding_result(
                "groundedness",
                0.0,
                start,
                reasoning=validation_error,
                error=validation_error,
            )

        try:
            response_emb, model, provider_name = await self._get_embedding(
                input_data.response, input_data
            )
            context_emb, _, _ = await self._get_embedding(input_data.context, input_data)
        except RuntimeError as exc:
            return self._build_embedding_result(
                "groundedness",
                0.0,
                start,
                reasoning=str(exc),
                error=str(exc),
            )

        groundedness = self._cosine_similarity(response_emb, context_emb)

        return self._build_embedding_result(
            "groundedness",
            groundedness,
            start,
            reasoning=f"Response-context groundedness: {groundedness:.4f}",
            metadata={
                "method": "cosine_similarity",
                "embedding_model": model,
                "embedding_provider": provider_name,
            },
        )
