"""Hallucination metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class HallucinationMetric(LLMJudgeMetric):
    """Evaluates hallucination in response using LLM-as-judge.

    Detects fabricated or unverifiable content that cannot be
    traced to the context or reference.
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="hallucination",
            display_name="Hallucination",
            description="Measures fabricated content not supported by context or reference",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            requires_context=True,
            tags=("quality", "safety", "rag", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )
