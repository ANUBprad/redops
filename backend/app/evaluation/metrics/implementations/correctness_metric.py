"""Correctness metric - measures factual correctness against reference."""

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


class CorrectnessMetric(Metric):
    """Evaluates factual correctness of a response against a reference answer.

    Uses token-level F1 scoring as a heuristic.
    In production, replace with LLM-based judge.
    """

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="correctness",
            display_name="Correctness",
            description="Measures factual correctness against reference answer",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "factual"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate correctness using token F1 against reference."""
        start = time.monotonic()

        if not input_data.response:
            return MetricResult(
                metric_name="correctness",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        if not input_data.reference:
            return MetricResult(
                metric_name="correctness",
                score=0.0,
                normalized_score=0.0,
                error="Missing reference answer for correctness comparison",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        response_tokens = input_data.response.lower().split()
        reference_tokens = input_data.reference.lower().split()

        if not reference_tokens:
            return MetricResult(
                metric_name="correctness",
                score=0.0,
                normalized_score=0.0,
                reasoning="Empty reference",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        ref_counts: dict[str, int] = {}
        for t in reference_tokens:
            ref_counts[t] = ref_counts.get(t, 0) + 1

        resp_counts: dict[str, int] = {}
        for t in response_tokens:
            resp_counts[t] = resp_counts.get(t, 0) + 1

        common = 0
        for token, count in resp_counts.items():
            if token in ref_counts:
                common += min(count, ref_counts[token])

        precision = 0.0 if not response_tokens else common / len(response_tokens)

        recall = 0.0 if not reference_tokens else common / len(reference_tokens)

        f1 = (
            0.0
            if precision + recall == 0
            else 2 * (precision * recall) / (precision + recall)
        )

        return MetricResult(
            metric_name="correctness",
            score=f1,
            normalized_score=min(f1, 1.0),
            reasoning=f"Token F1: precision={precision:.3f}, recall={recall:.3f}",
            metadata={"precision": precision, "recall": recall, "common_tokens": common},
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
