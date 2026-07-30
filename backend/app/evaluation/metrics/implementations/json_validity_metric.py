"""JSON validity metric - validates response is parseable JSON."""

from __future__ import annotations

import json
import time

from app.evaluation.metrics.domain import (
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)


class JsonValidityMetric(Metric):
    """Evaluates whether the response is valid JSON.

    Returns binary score: 1.0 if valid, 0.0 if not.
    """

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="json_validity",
            display_name="JSON Validity",
            description="Validates that the response is parseable JSON",
            category=MetricCategory.VALIDATION,
            scale=MetricScale.BINARY,
            tags=("validation", "format"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate JSON validity."""
        start = time.monotonic()

        if not input_data.response:
            return MetricResult(
                metric_name="json_validity",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            parsed = json.loads(input_data.response)
            is_valid = isinstance(parsed, (dict, list))
            score = 1.0 if is_valid else 0.0
            reasoning = "Valid JSON" if is_valid else "JSON parsed but not object/array"
        except (json.JSONDecodeError, ValueError) as exc:
            score = 0.0
            reasoning = f"Invalid JSON: {exc}"
            is_valid = False

        return MetricResult(
            metric_name="json_validity",
            score=score,
            normalized_score=score,
            reasoning=reasoning,
            metadata={"is_valid": is_valid},
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
