"""Reasoning Quality metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class ReasoningQualityMetric(LLMJudgeMetric):
    """Evaluates the logical quality and completeness of reasoning."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="reasoning_quality",
            display_name="Reasoning Quality",
            description="Measures logical quality and completeness of reasoning in the response",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "reasoning", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response"),
        )
