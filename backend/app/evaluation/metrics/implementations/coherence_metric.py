"""Coherence metric — LLM judge-based evaluation."""

from __future__ import annotations

from app.evaluation.metrics.domain import (
    MetricCategory,
    MetricDefinition,
    MetricScale,
)
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric


class CoherenceMetric(LLMJudgeMetric):
    """Evaluates how well-structured and logical the response is."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="coherence",
            display_name="Coherence",
            description="Measures how well-structured and logical the response is",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "structure", "llm_judge"),
        )
