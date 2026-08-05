"""Response Length metric — measures response length efficiency."""

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


class ResponseLengthMetric(Metric):
    """Measures response length relative to expected length.

    Scores responses that match the expected length range higher.
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="response_length",
            display_name="Response Length",
            description="Measures response length efficiency relative to expected length",
            category=MetricCategory.VALIDATION,
            scale=MetricScale.CONTINUOUS,
            tags=("validation", "length"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        if not input_data.response:
            return MetricResult(
                metric_name="response_length",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        response_length = len(input_data.response)
        word_count = len(input_data.response.split())

        expected_min = input_data.metadata.get("expected_min_length", 0)
        expected_max = input_data.metadata.get("expected_max_length", 10000)
        expected_words = input_data.metadata.get("expected_word_count", 0)

        if expected_words > 0:
            word_ratio = word_count / expected_words
            score = max(0.0, 1.0 - abs(1.0 - word_ratio))
        elif expected_max > expected_min:
            mid = (expected_min + expected_max) / 2
            half_range = (expected_max - expected_min) / 2
            if half_range > 0:
                score = max(0.0, 1.0 - abs(response_length - mid) / half_range)
            else:
                score = 1.0 if response_length == expected_min else 0.0
        else:
            score = 1.0 if response_length > 0 else 0.0

        return MetricResult(
            metric_name="response_length",
            score=float(response_length),
            normalized_score=max(0.0, min(1.0, score)),
            reasoning=f"Response: {response_length} chars, {word_count} words",
            metadata={
                "char_count": response_length,
                "word_count": word_count,
                "expected_min": expected_min,
                "expected_max": expected_max,
            },
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
