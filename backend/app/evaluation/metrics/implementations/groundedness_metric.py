"""Groundedness metric - measures if response is grounded in context."""

from __future__ import annotations

import time

from app.evaluation.metrics.domain import (
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)


class GroundednessMetric(Metric):
    """Evaluates whether the response is supported by the provided context.

    Uses sentence-level claim detection with context verification.
    In production, replace with NLI model or LLM-based evaluation.
    """

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="groundedness",
            display_name="Groundedness",
            description="Measures if the response is supported by the context",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            requires_context=True,
            tags=("quality", "faithfulness", "rag"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        """Validate that context is provided."""
        if not input_data.context:
            return "Groundedness requires context to evaluate against"
        return None

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate groundedness by checking claim support in context."""
        start = time.monotonic()

        if not input_data.response:
            return MetricResult(
                metric_name="groundedness",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        validation_error = self.validate_input(input_data)
        if validation_error:
            return MetricResult(
                metric_name="groundedness",
                score=0.0,
                normalized_score=0.0,
                error=validation_error,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        sentences = [s.strip() for s in input_data.response.split(".") if s.strip()]
        context_lower = input_data.context.lower()

        grounded_count = 0
        for sentence in sentences:
            words = set(sentence.lower().split())
            context_words = set(context_lower.split())
            overlap = words & context_words
            if len(words) > 0 and len(overlap) / len(words) > 0.3:
                grounded_count += 1

        score = 0.0 if not sentences else grounded_count / len(sentences)

        return MetricResult(
            metric_name="groundedness",
            score=score,
            normalized_score=min(score, 1.0),
            reasoning=f"{grounded_count}/{len(sentences)} claims appear grounded in context",
            metadata={
                "grounded_claims": grounded_count,
                "total_claims": len(sentences),
            },
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
