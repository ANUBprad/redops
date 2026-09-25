"""Toxicity metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class ToxicityMetric(LLMJudgeMetric):
    """Evaluates the presence of toxic or offensive language."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="toxicity",
            display_name="Toxicity",
            description="Measures the presence of toxic or offensive language",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "safety", "toxicity", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response"),
        )
