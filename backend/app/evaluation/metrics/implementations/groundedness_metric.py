"""Groundedness metric — LLM judge-backed evaluation.

Evaluates whether claims in the response are supported by the supplied
context/evidence using the LLM-as-judge pipeline. This replaces the
previous embedding-based (cosine similarity) implementation with a
semantically richer evaluation that distinguishes fully grounded,
partially grounded, and ungrounded responses.
"""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class GroundednessMetric(LLMJudgeMetric):
    """Evaluates whether response claims are supported by context using LLM-as-judge.

    Measures if the response is semantically supported by the provided
    context, distinguishing fully grounded, partially grounded, and
    ungrounded responses via a structured judge verdict.
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="groundedness",
            display_name="Groundedness",
            description="Measures whether claims in the response are supported by the context",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            requires_context=True,
            tags=("quality", "faithfulness", "rag", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        if not input_data.context:
            return "Groundedness requires context to evaluate against"
        return None
