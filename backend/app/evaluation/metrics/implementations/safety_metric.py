"""Safety metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class SafetyMetric(LLMJudgeMetric):
    """Evaluates whether the response contains harmful or dangerous content."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="safety",
            display_name="Safety",
            description="Measures whether the response contains harmful or dangerous content",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "safety", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )
