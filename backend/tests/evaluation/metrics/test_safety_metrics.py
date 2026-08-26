"""Tests for prompt injection and jailbreak metrics.

Validates definition, registration in ALL_METRICS, and that they
are recognized as LLM judge metrics.
"""

from __future__ import annotations

from app.evaluation.metrics.domain import MetricCategory, MetricScale
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.metrics.implementations.jailbreak_metric import JailbreakMetric
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric
from app.evaluation.metrics.implementations.prompt_injection_metric import (
    PromptInjectionMetric,
)


class TestPromptInjectionMetric:
    """PromptInjectionMetric definition and registration."""

    def test_registered_in_all_metrics(self) -> None:
        assert PromptInjectionMetric in ALL_METRICS

    def test_is_llm_judge_metric(self) -> None:
        assert issubclass(PromptInjectionMetric, LLMJudgeMetric)

    def test_definition(self) -> None:
        metric = PromptInjectionMetric()
        defn = metric.definition()
        assert defn.name == "prompt_injection"
        assert defn.display_name == "Prompt Injection"
        assert defn.category == MetricCategory.QUALITY
        assert defn.scale == MetricScale.CONTINUOUS
        assert "safety" in defn.tags
        assert "injection" in defn.tags
        assert "llm_judge" in defn.tags


class TestJailbreakMetric:
    """JailbreakMetric definition and registration."""

    def test_registered_in_all_metrics(self) -> None:
        assert JailbreakMetric in ALL_METRICS

    def test_is_llm_judge_metric(self) -> None:
        assert issubclass(JailbreakMetric, LLMJudgeMetric)

    def test_definition(self) -> None:
        metric = JailbreakMetric()
        defn = metric.definition()
        assert defn.name == "jailbreak"
        assert defn.display_name == "Jailbreak"
        assert defn.category == MetricCategory.QUALITY
        assert defn.scale == MetricScale.CONTINUOUS
        assert "safety" in defn.tags
        assert "jailbreak" in defn.tags
        assert "llm_judge" in defn.tags
