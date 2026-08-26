"""Latency metric - measures response time."""

from __future__ import annotations

import time

from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.implementations._measurement import as_number


class LatencyMetric(Metric):
    """Evaluates response latency from metadata.

    Reads latency_ms from input metadata. Lower latency scores higher.
    Uses a configurable threshold with logarithmic scaling.
    """

    DEFAULT_THRESHOLD_MS = 5000

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="latency",
            display_name="Latency",
            description="Measures response time (lower is better)",
            category=MetricCategory.PERFORMANCE,
            scale=MetricScale.CONTINUOUS,
            evaluator_type=EvaluatorType.HEURISTIC,
            required_inputs=("metadata",),
            tags=("performance", "speed"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate latency using metadata latency_ms value."""
        start = time.monotonic()

        if "latency_ms" not in input_data.metadata:
            return MetricResult(
                metric_name="latency",
                score=0.0,
                normalized_score=0.0,
                reasoning="latency_ms not provided in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error="latency_ms not provided in metadata",
            )

        latency_ms = as_number(input_data.metadata.get("latency_ms"))
        if latency_ms is None:
            return MetricResult(
                metric_name="latency",
                score=0.0,
                normalized_score=0.0,
                error="Invalid latency_ms in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        if latency_ms <= 0:
            return MetricResult(
                metric_name="latency",
                score=1.0,
                normalized_score=1.0,
                reasoning="No latency recorded (instantaneous or unavailable)",
                metadata={"latency_ms": latency_ms},
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        import math

        threshold = self.DEFAULT_THRESHOLD_MS
        score = max(0.0, 1.0 - math.log1p(latency_ms) / math.log1p(threshold))
        normalized = max(0.0, min(score, 1.0))

        return MetricResult(
            metric_name="latency",
            score=latency_ms,
            normalized_score=normalized,
            reasoning=f"Latency: {latency_ms}ms (threshold: {threshold}ms)",
            metadata={"latency_ms": latency_ms, "threshold_ms": threshold},
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
