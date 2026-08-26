"""Instruction Following metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class InstructionFollowingMetric(LLMJudgeMetric):
    """Evaluates how well the response follows the original instructions."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="instruction_following",
            display_name="Instruction Following",
            description="Measures how well the response follows the given instructions",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "instruction", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response"),
        )
