"""Context Relevance metric — embedding-based evaluation."""

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


class ContextRelevanceMetric(EmbeddingMetric):
    """Evaluates how relevant the context is to the prompt using embeddings."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="context_relevance",
            display_name="Context Relevance",
            description="Measures how relevant the context is to the prompt",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            evaluator_type=EvaluatorType.EMBEDDING,
            required_inputs=("prompt", "context"),
            requires_context=True,
            tags=("quality", "rag", "relevance", "embedding"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        if not input_data.context:
            return "Context relevance requires context to evaluate"
        return None

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        validation_error = self.validate_input(input_data)
        if validation_error:
            return self._build_embedding_result(
                "context_relevance",
                0.0,
                start,
                reasoning=validation_error,
                error=validation_error,
            )

        try:
            prompt_emb, model, provider_name = await self._get_embedding(
                input_data.prompt, input_data
            )
            context_emb, _, _ = await self._get_embedding(input_data.context, input_data)
        except RuntimeError as exc:
            return self._build_embedding_result(
                "context_relevance",
                0.0,
                start,
                reasoning=str(exc),
                error=str(exc),
            )

        relevance = self._cosine_similarity(prompt_emb, context_emb)

        return self._build_embedding_result(
            "context_relevance",
            relevance,
            start,
            reasoning=f"Prompt-context relevance: {relevance:.4f}",
            metadata={
                "method": "cosine_similarity",
                "embedding_model": model,
                "embedding_provider": provider_name,
            },
        )
