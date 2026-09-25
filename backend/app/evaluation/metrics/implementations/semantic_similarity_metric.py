"""Semantic Similarity metric — embedding-based evaluation."""

from __future__ import annotations

import time

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.implementations.embedding_base import EmbeddingMetric


class SemanticSimilarityMetric(EmbeddingMetric):
    """Evaluates semantic similarity between response and reference using embeddings."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="semantic_similarity",
            display_name="Semantic Similarity",
            description="Measures semantic similarity between response and reference using embeddings",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            evaluator_type=EvaluatorType.EMBEDDING,
            required_inputs=("response", "reference"),
            tags=("quality", "semantic", "embedding"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        if not input_data.reference:
            return "Semantic similarity requires a reference answer"
        return None

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        if not input_data.response:
            return self._build_embedding_result(
                "semantic_similarity",
                0.0,
                start,
                error="Missing response",
            )

        validation_error = self.validate_input(input_data)
        if validation_error:
            return self._build_embedding_result(
                "semantic_similarity",
                0.0,
                start,
                reasoning=validation_error,
                error=validation_error,
            )

        try:
            response_emb, model, provider_name = await self._get_embedding(
                input_data.response, input_data
            )
            reference_emb, _, _ = await self._get_embedding(input_data.reference, input_data)
        except RuntimeError as exc:
            return self._build_embedding_result(
                "semantic_similarity",
                0.0,
                start,
                reasoning=str(exc),
                error=str(exc),
            )

        similarity = self._cosine_similarity(response_emb, reference_emb)

        return self._build_embedding_result(
            "semantic_similarity",
            similarity,
            start,
            reasoning=f"Cosine similarity: {similarity:.4f}",
            metadata={
                "embedding_dimensions": len(response_emb),
                "method": "cosine_similarity",
                "embedding_model": model,
                "embedding_provider": provider_name,
            },
        )
