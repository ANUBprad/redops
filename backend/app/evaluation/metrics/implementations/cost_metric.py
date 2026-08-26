"""Cost metric - measures API cost efficiency."""

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


class CostMetric(Metric):
    """Evaluates cost efficiency of the API call.

    Scores based on USD cost from metadata. Lower cost scores higher.
    Uses logarithmic scaling against a configurable threshold.
    """

    DEFAULT_MAX_COST_USD = 0.10

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="cost",
            display_name="Cost",
            description="Measures API cost efficiency (lower is better)",
            category=MetricCategory.COST,
            scale=MetricScale.CONTINUOUS,
            evaluator_type=EvaluatorType.HEURISTIC,
            required_inputs=("metadata",),
            tags=("cost", "efficiency"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate cost from metadata."""
        start = time.monotonic()

        if "cost_usd" not in input_data.metadata:
            return MetricResult(
                metric_name="cost",
                score=0.0,
                normalized_score=0.0,
                reasoning="cost_usd not provided in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error="cost_usd not provided in metadata",
            )

        cost_usd = as_number(input_data.metadata.get("cost_usd"))
        if cost_usd is None:
            return MetricResult(
                metric_name="cost",
                score=0.0,
                normalized_score=0.0,
                error="Invalid cost_usd in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        max_cost = self.DEFAULT_MAX_COST_USD

        if cost_usd <= 0:
            score = 1.0
        else:
            import math

            score = max(0.0, 1.0 - math.log1p(cost_usd) / math.log1p(max_cost))

        return MetricResult(
            metric_name="cost",
            score=cost_usd,
            normalized_score=max(0.0, min(score, 1.0)),
            reasoning=f"Cost: ${cost_usd:.6f} (threshold: ${max_cost})",
            metadata={"cost_usd": cost_usd, "max_cost_usd": max_cost},
            version=self.definition().version,
            cost_usd=cost_usd,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
