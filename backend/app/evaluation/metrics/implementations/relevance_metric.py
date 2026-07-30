"""Relevance metric - measures how relevant the response is to the prompt."""

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


class RelevanceMetric(Metric):
    """Evaluates how relevant a model response is to the given prompt.

    Uses keyword overlap and semantic similarity heuristics.
    In production, replace with LLM-based evaluation.
    """

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="relevance",
            display_name="Relevance",
            description="Measures how relevant the response is to the prompt",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "semantic"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate relevance using keyword overlap heuristic."""
        start = time.monotonic()

        if not input_data.prompt or not input_data.response:
            return MetricResult(
                metric_name="relevance",
                score=0.0,
                normalized_score=0.0,
                error="Missing prompt or response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        prompt_words = set(input_data.prompt.lower().split())
        response_words = set(input_data.response.lower().split())

        if not prompt_words:
            return MetricResult(
                metric_name="relevance",
                score=0.0,
                normalized_score=0.0,
                reasoning="Empty prompt",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        overlap = prompt_words & response_words
        score = len(overlap) / len(prompt_words)

        return MetricResult(
            metric_name="relevance",
            score=score,
            normalized_score=min(score, 1.0),
            reasoning=f"Keyword overlap: {len(overlap)}/{len(prompt_words)} prompt terms found in response",
            metadata={"overlap_words": sorted(overlap)},
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
