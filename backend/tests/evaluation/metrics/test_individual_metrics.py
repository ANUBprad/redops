"""Tests for individual metric implementations."""

from __future__ import annotations

import pytest

from app.evaluation.metrics.domain import MetricCategory, MetricInput, MetricScale
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.metrics.implementations.correctness_metric import CorrectnessMetric
from app.evaluation.metrics.implementations.cost_metric import CostMetric
from app.evaluation.metrics.implementations.faithfulness_metric import FaithfulnessMetric
from app.evaluation.metrics.implementations.groundedness_metric import GroundednessMetric
from app.evaluation.metrics.implementations.hallucination_metric import HallucinationMetric
from app.evaluation.metrics.implementations.json_validity_metric import JsonValidityMetric
from app.evaluation.metrics.implementations.latency_metric import LatencyMetric
from app.evaluation.metrics.implementations.relevance_metric import RelevanceMetric
from app.evaluation.metrics.implementations.token_usage_metric import TokenUsageMetric
from app.evaluation.metrics.implementations.tool_call_correctness_metric import (
    ToolCallCorrectnessMetric,
)


class TestAllMetricsHaveDefinitions:
    """Every registered metric must have a valid definition."""

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_definition_valid(self, metric_cls: type) -> None:
        """Metric definition has required fields."""
        metric = metric_cls()
        defn = metric.definition()
        assert defn.name
        assert defn.display_name
        assert defn.description
        assert isinstance(defn.category, MetricCategory)
        assert isinstance(defn.scale, MetricScale)


class TestRelevanceMetric:
    """Tests for RelevanceMetric."""

    @pytest.mark.asyncio
    async def test_relevant_response(self) -> None:
        """Response containing prompt keywords scores high."""
        metric = RelevanceMetric()
        result = await metric.evaluate(
            MetricInput(prompt="machine learning", response="machine learning is great"),
        )
        assert result.is_success
        assert result.normalized_score > 0.5

    @pytest.mark.asyncio
    async def test_irrelevant_response(self) -> None:
        """Response without prompt keywords scores low."""
        metric = RelevanceMetric()
        result = await metric.evaluate(
            MetricInput(prompt="quantum physics", response="cooking recipes"),
        )
        assert result.is_success
        assert result.normalized_score < 0.5

    @pytest.mark.asyncio
    async def test_empty_response(self) -> None:
        """Empty response returns error."""
        metric = RelevanceMetric()
        result = await metric.evaluate(MetricInput(prompt="test"))
        assert not result.is_success
        assert result.error is not None


class TestCorrectnessMetric:
    """Tests for CorrectnessMetric."""

    @pytest.mark.asyncio
    async def test_exact_match(self) -> None:
        """Exact match with reference scores 1.0."""
        metric = CorrectnessMetric()
        result = await metric.evaluate(
            MetricInput(response="the answer is 42", reference="the answer is 42"),
        )
        assert result.is_success
        assert result.normalized_score == 1.0

    @pytest.mark.asyncio
    async def test_no_match(self) -> None:
        """Completely different response scores 0."""
        metric = CorrectnessMetric()
        result = await metric.evaluate(
            MetricInput(response="abc", reference="xyz"),
        )
        assert result.is_success
        assert result.normalized_score == 0.0

    @pytest.mark.asyncio
    async def test_missing_reference(self) -> None:
        """Missing reference returns error."""
        metric = CorrectnessMetric()
        result = await metric.evaluate(MetricInput(response="test"))
        assert not result.is_success


class TestGroundednessMetric:
    """Tests for GroundednessMetric."""

    @pytest.mark.asyncio
    async def test_grounded_response(self) -> None:
        """Response grounded in context scores high."""
        metric = GroundednessMetric()
        result = await metric.evaluate(
            MetricInput(
                response="Python is a programming language",
                context="Python is a popular programming language used worldwide",
            ),
        )
        assert result.is_success
        assert result.normalized_score > 0.0

    @pytest.mark.asyncio
    async def test_missing_context(self) -> None:
        """Missing context returns error."""
        metric = GroundednessMetric()
        result = await metric.evaluate(MetricInput(response="test"))
        assert not result.is_success


class TestHallucinationMetric:
    """Tests for HallucinationMetric."""

    @pytest.mark.asyncio
    async def test_grounded_few_hallucinations(self) -> None:
        """Response grounded in context has low hallucination."""
        metric = HallucinationMetric()
        result = await metric.evaluate(
            MetricInput(
                response="The sky is blue. Water is wet.",
                context="The sky appears blue due to Rayleigh scattering. Water is wet.",
            ),
        )
        assert result.is_success
        assert result.normalized_score < 0.8


class TestFaithfulnessMetric:
    """Tests for FaithfulnessMetric."""

    @pytest.mark.asyncio
    async def test_faithful_response(self) -> None:
        """Response faithful to context scores high."""
        metric = FaithfulnessMetric()
        result = await metric.evaluate(
            MetricInput(
                response="Python is a language. It is popular.",
                context="Python is a popular programming language used worldwide.",
            ),
        )
        assert result.is_success
        assert result.normalized_score > 0.0


class TestLatencyMetric:
    """Tests for LatencyMetric."""

    @pytest.mark.asyncio
    async def test_low_latency(self) -> None:
        """Low latency scores high."""
        metric = LatencyMetric()
        result = await metric.evaluate(
            MetricInput(metadata={"latency_ms": 100}),
        )
        assert result.is_success
        assert result.normalized_score > 0.3

    @pytest.mark.asyncio
    async def test_high_latency(self) -> None:
        """High latency scores low."""
        metric = LatencyMetric()
        result = await metric.evaluate(
            MetricInput(metadata={"latency_ms": 10000}),
        )
        assert result.is_success
        assert result.normalized_score < 0.5


class TestTokenUsageMetric:
    """Tests for TokenUsageMetric."""

    @pytest.mark.asyncio
    async def test_low_usage(self) -> None:
        """Low token usage scores high."""
        metric = TokenUsageMetric()
        result = await metric.evaluate(
            MetricInput(metadata={"tokens_output": 10}),
        )
        assert result.is_success
        assert result.normalized_score > 0.5

    @pytest.mark.asyncio
    async def test_high_usage(self) -> None:
        """High token usage scores low."""
        metric = TokenUsageMetric()
        result = await metric.evaluate(
            MetricInput(metadata={"tokens_output": 5000}),
        )
        assert result.is_success
        assert result.normalized_score < 0.5


class TestCostMetric:
    """Tests for CostMetric."""

    @pytest.mark.asyncio
    async def test_low_cost(self) -> None:
        """Low cost scores high."""
        metric = CostMetric()
        result = await metric.evaluate(
            MetricInput(metadata={"cost_usd": 0.001}),
        )
        assert result.is_success
        assert result.normalized_score > 0.5

    @pytest.mark.asyncio
    async def test_high_cost(self) -> None:
        """High cost scores low."""
        metric = CostMetric()
        result = await metric.evaluate(
            MetricInput(metadata={"cost_usd": 1.0}),
        )
        assert result.is_success
        assert result.normalized_score < 0.5


class TestJsonValidityMetric:
    """Tests for JsonValidityMetric."""

    @pytest.mark.asyncio
    async def test_valid_json(self) -> None:
        """Valid JSON scores 1.0."""
        metric = JsonValidityMetric()
        result = await metric.evaluate(
            MetricInput(response='{"key": "value"}'),
        )
        assert result.is_success
        assert result.normalized_score == 1.0

    @pytest.mark.asyncio
    async def test_valid_json_array(self) -> None:
        """Valid JSON array scores 1.0."""
        metric = JsonValidityMetric()
        result = await metric.evaluate(
            MetricInput(response='[1, 2, 3]'),
        )
        assert result.is_success
        assert result.normalized_score == 1.0

    @pytest.mark.asyncio
    async def test_invalid_json(self) -> None:
        """Invalid JSON scores 0.0."""
        metric = JsonValidityMetric()
        result = await metric.evaluate(
            MetricInput(response="not json at all"),
        )
        assert result.is_success
        assert result.normalized_score == 0.0

    @pytest.mark.asyncio
    async def test_json_primitive(self) -> None:
        """JSON primitive (string/number) scores 0.0."""
        metric = JsonValidityMetric()
        result = await metric.evaluate(
            MetricInput(response='"just a string"'),
        )
        assert result.is_success
        assert result.normalized_score == 0.0


class TestToolCallCorrectnessMetric:
    """Tests for ToolCallCorrectnessMetric."""

    @pytest.mark.asyncio
    async def test_valid_tool_calls(self) -> None:
        """Valid tool calls score 1.0."""
        metric = ToolCallCorrectnessMetric()
        result = await metric.evaluate(
            MetricInput(
                tool_calls=(
                    {"name": "search", "arguments": {"query": "test"}},
                ),
            ),
        )
        assert result.is_success
        assert result.normalized_score == 1.0

    @pytest.mark.asyncio
    async def test_no_tool_calls(self) -> None:
        """No tool calls score 1.0 (nothing to validate)."""
        metric = ToolCallCorrectnessMetric()
        result = await metric.evaluate(MetricInput())
        assert result.is_success
        assert result.normalized_score == 1.0

    @pytest.mark.asyncio
    async def test_invalid_tool_call(self) -> None:
        """Invalid tool call scores lower."""
        metric = ToolCallCorrectnessMetric()
        result = await metric.evaluate(
            MetricInput(
                tool_calls=(
                    {"arguments": {"query": "test"}},  # missing 'name'
                ),
            ),
        )
        assert result.is_success
        assert result.normalized_score == 0.0

    @pytest.mark.asyncio
    async def test_json_arguments(self) -> None:
        """JSON string arguments are parsed correctly."""
        metric = ToolCallCorrectnessMetric()
        result = await metric.evaluate(
            MetricInput(
                tool_calls=(
                    {"name": "search", "arguments": '{"query": "test"}'},
                ),
            ),
        )
        assert result.is_success
        assert result.normalized_score == 1.0
