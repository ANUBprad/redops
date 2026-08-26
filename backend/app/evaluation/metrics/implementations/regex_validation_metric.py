"""Regex Validation metric — validates response matches a regex pattern."""

from __future__ import annotations

import re
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


class RegexValidationMetric(Metric):
    """Validates that the response matches a regex pattern.

    The pattern is provided via input_data.metadata["regex_pattern"].
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="regex_validation",
            display_name="Regex Validation",
            description="Validates that the response matches a regex pattern",
            category=MetricCategory.VALIDATION,
            scale=MetricScale.BINARY,
            evaluator_type=EvaluatorType.HEURISTIC,
            required_inputs=("response",),
            tags=("validation", "format", "regex"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        if not input_data.response:
            return MetricResult(
                metric_name="regex_validation",
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        pattern = input_data.metadata.get("regex_pattern")
        if not pattern or not isinstance(pattern, str):
            return MetricResult(
                metric_name="regex_validation",
                score=0.0,
                normalized_score=0.0,
                error="No regex_pattern provided in metadata",
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            match = re.search(pattern, input_data.response, re.DOTALL)
            is_valid = match is not None
            score = 1.0 if is_valid else 0.0
            reasoning = (
                f"Response matches pattern '{pattern}'"
                if is_valid
                else f"Response does not match pattern '{pattern}'"
            )
        except re.error as exc:
            score = 0.0
            reasoning = f"Invalid regex pattern: {exc}"
            is_valid = False

        return MetricResult(
            metric_name="regex_validation",
            score=score,
            normalized_score=score,
            reasoning=reasoning,
            metadata={"pattern": pattern, "matched": is_valid},
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
