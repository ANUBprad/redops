"""Faithfulness metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class FaithfulnessMetric(LLMJudgeMetric):
    """Evaluates faithfulness of response to context using LLM-as-judge.

    Measures whether the response only contains information
    derivable from the provided context.
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="faithfulness",
            display_name="Faithfulness",
            description="Measures alignment of response with source context using LLM judge",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            requires_context=True,
            tags=("quality", "rag", "consistency", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )

    def validate_input(self, input_data: MetricInput) -> str | None:
        if not input_data.context:
            return "Faithfulness requires context to evaluate against"
        return None
