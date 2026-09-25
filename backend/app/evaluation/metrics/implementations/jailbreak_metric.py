"""Jailbreak metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class JailbreakMetric(LLMJudgeMetric):
    """Evaluates whether the response indicates a successful jailbreak."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="jailbreak",
            display_name="Jailbreak",
            description="Measures whether the response indicates a successful jailbreak attempt",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "safety", "jailbreak", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )
