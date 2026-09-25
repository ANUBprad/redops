"""Example custom accuracy metric plugin for RedOps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evaluation.metrics.domain import (
    BaseMetric,
    EvaluatorType,
    MetricCategory,
    MetricResult,
    MetricScale,
    ScoreDirection,
)


@dataclass
class CustomAccuracyMetric(BaseMetric):
    """Example custom accuracy metric.

    Computes a simple exact-match or fuzzy-match accuracy score
    between expected and actual outputs.
    """

    name: str = "custom_accuracy"
    display_name: str = "Custom Accuracy"
    description: str = "Exact-match or fuzzy-match accuracy score"
    category: MetricCategory = MetricCategory.CORRECTNESS
    scale: MetricScale = MetricScale.ZERO_TO_ONE
    version: str = "1.0.0"
    evaluator_type: EvaluatorType = EvaluatorType.CUSTOM
    required_inputs: tuple[str, ...] = ("expected_output", "actual_output")
    default_weight: float = 1.0
    direction: ScoreDirection = ScoreDirection.HIGHER_IS_BETTER
    default_threshold: float = 0.8
    requires_context: bool = False
    tags: tuple[str, ...] = ("accuracy", "exact-match", "fuzzy-match")

    def evaluate(self, *, inputs: dict[str, Any], context: dict[str, Any] | None = None) -> MetricResult:
        expected = str(inputs.get("expected_output", "")).strip()
        actual = str(inputs.get("actual_output", "")).strip()

        if not expected:
            return MetricResult(
                metric_name=self.name,
                score=0.0,
                normalized_score=0.0,
                raw_output="No expected output provided",
                reasoning="Cannot evaluate without expected output",
                confidence=0.0,
                version=self.version,
            )

        # Exact match
        if expected.lower() == actual.lower():
            score = 1.0
            reasoning = "Exact match (case-insensitive)"
        # Fuzzy: check if expected is contained in actual or vice versa
        elif expected.lower() in actual.lower() or actual.lower() in expected.lower():
            score = 0.7
            reasoning = "Partial match (substring)"
        else:
            score = 0.0
            reasoning = "No match"

        return MetricResult(
            metric_name=self.name,
            score=score,
            normalized_score=score,
            raw_output=f"expected={expected!r}, actual={actual!r}",
            reasoning=reasoning,
            confidence=1.0,
            version=self.version,
        )
