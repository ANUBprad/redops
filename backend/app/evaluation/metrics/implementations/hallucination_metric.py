"""Hallucination metric - measures fabricated content in response."""

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


class HallucinationMetric(Metric):
    """Evaluates the degree of hallucination in a response.

    Detects unsupported claims by checking if response content
    can be traced to the context or reference.
    In production, use NLI models or dedicated hallucination detectors.
    """

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="hallucination",
            display_name="Hallucination",
            description="Measures fabricated content not supported by context or reference",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            requires_context=True,
            tags=("quality", "safety", "rag"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate hallucination by checking unsupported claims."""
        start = time.monotonic()

        if not input_data.response:
            return MetricResult(
                metric_name="hallucination",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        sentences = [s.strip() for s in input_data.response.split(".") if s.strip()]
        if not sentences:
            return MetricResult(
                metric_name="hallucination",
                score=0.0,
                normalized_score=0.0,
                reasoning="No sentences to analyze",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        support_sources = " ".join(
            [input_data.context, input_data.reference],
        ).lower()
        support_words = set(support_sources.split()) if support_sources else set()

        hallucinated = 0
        for sentence in sentences:
            words = set(sentence.lower().split())
            if not words:
                continue
            if support_words:
                overlap = words & support_words
                support_ratio = len(overlap) / len(words)
            else:
                support_ratio = 0.0

            if support_ratio < 0.2:
                hallucinated += 1

        score = hallucinated / len(sentences)
        normalized = min(score, 1.0)

        return MetricResult(
            metric_name="hallucination",
            score=score,
            normalized_score=normalized,
            reasoning=f"{hallucinated}/{len(sentences)} sentences appear hallucinated",
            metadata={
                "hallucinated_sentences": hallucinated,
                "total_sentences": len(sentences),
            },
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
