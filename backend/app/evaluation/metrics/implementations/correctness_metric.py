"""Correctness metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class CorrectnessMetric(LLMJudgeMetric):
    """Evaluates factual correctness of a response using LLM-as-judge.

    Compares the response against a reference answer and judges
    factual accuracy, completeness, and correctness.
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="correctness",
            display_name="Correctness",
            description="Measures factual correctness against reference answer using LLM judge",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "factual", "llm_judge"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        if not input_data.reference:
            return "Correctness requires a reference answer"
        return None
