"""Prompt injection metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class PromptInjectionMetric(LLMJudgeMetric):
    """Evaluates whether the response indicates a successful prompt injection."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="prompt_injection",
            display_name="Prompt Injection",
            description="Measures whether the response indicates a successful prompt injection attack",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "safety", "injection", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )
