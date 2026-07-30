"""Faithfulness metric - measures alignment with source material."""

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


class FaithfulnessMetric(Metric):
    """Evaluates faithfulness of the response to the provided context.

    Measures whether the response only contains information that
    can be derived from the context, without adding unsupported claims.
    """

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="faithfulness",
            display_name="Faithfulness",
            description="Measures alignment of response with source context",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            requires_context=True,
            tags=("quality", "rag", "consistency"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        """Validate that context is provided."""
        if not input_data.context:
            return "Faithfulness requires context to evaluate against"
        return None

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate faithfulness by checking context alignment."""
        start = time.monotonic()

        if not input_data.response:
            return MetricResult(
                metric_name="faithfulness",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        validation_error = self.validate_input(input_data)
        if validation_error:
            return MetricResult(
                metric_name="faithfulness",
                score=0.0,
                normalized_score=0.0,
                error=validation_error,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        response_sentences = [
            s.strip() for s in input_data.response.split(".") if s.strip()
        ]
        context_sentences = [
            s.strip() for s in input_data.context.split(".") if s.strip()
        ]

        if not response_sentences:
            return MetricResult(
                metric_name="faithfulness",
                score=0.0,
                normalized_score=0.0,
                reasoning="No response sentences to analyze",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        faithful_count = 0
        for resp_sent in response_sentences:
            resp_words = set(resp_sent.lower().split())
            for ctx_sent in context_sentences:
                ctx_words = set(ctx_sent.lower().split())
                if resp_words and ctx_words:
                    overlap = resp_words & ctx_words
                    similarity = len(overlap) / min(len(resp_words), len(ctx_words))
                    if similarity > 0.4:
                        faithful_count += 1
                        break

        score = faithful_count / len(response_sentences)

        return MetricResult(
            metric_name="faithfulness",
            score=score,
            normalized_score=min(score, 1.0),
            reasoning=f"{faithful_count}/{len(response_sentences)} sentences are faithful to context",
            metadata={
                "faithful_sentences": faithful_count,
                "total_sentences": len(response_sentences),
            },
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
