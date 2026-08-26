"""Answer Relevance metric — embedding-based evaluation."""

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


class AnswerRelevanceMetric(EmbeddingMetric):
    """Evaluates how relevant the response is to the prompt using embeddings."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="answer_relevance",
            display_name="Answer Relevance",
            description="Measures how relevant the response is to the prompt using embeddings",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "relevance", "embedding"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        if not input_data.prompt or not input_data.response:
            return self._build_embedding_result(
                "answer_relevance",
                0.0,
                start,
                reasoning="Missing prompt or response",
                error="Missing prompt or response",
            )

        try:
            prompt_emb, model, provider_name = await self._get_embedding(
                input_data.prompt, input_data
            )
            response_emb, _, _ = await self._get_embedding(input_data.response, input_data)
        except RuntimeError as exc:
            return self._build_embedding_result(
                "answer_relevance",
                0.0,
                start,
                reasoning=str(exc),
                error=str(exc),
            )

        relevance = self._cosine_similarity(prompt_emb, response_emb)

        return self._build_embedding_result(
            "answer_relevance",
            relevance,
            start,
            reasoning=f"Prompt-response relevance: {relevance:.4f}",
            metadata={
                "method": "cosine_similarity",
                "embedding_model": model,
                "embedding_provider": provider_name,
            },
        )
