"""Bias metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class BiasMetric(LLMJudgeMetric):
    """Evaluates the presence of unfair bias in the response."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="bias",
            display_name="Bias",
            description="Measures the presence of unfair bias in the response",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "safety", "bias", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )
