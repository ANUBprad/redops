"""Golden evaluation suite with deterministic metric expectations.

Defines canonical evaluation cases with expected metric outcomes.
Deterministic metrics use exact expected values. Embedding/judge
metrics use scripted providers with known outputs.
"""

from __future__ import annotations

import pytest

from app.evaluation.metrics.domain import MetricInput, MetricResult
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations import ALL_METRICS
from tests.evaluation.fixtures.canonical_items import CANONICAL_ITEMS, get_item
from tests.evaluation.metrics.test_score_contract import (
    DeterministicEmbeddingProvider,
    ScriptedJudgeProvider,
)


def _make_engine() -> MetricEngine:
    """Create a metric engine with all metrics registered."""
    engine = MetricEngine()
    for metric_cls in ALL_METRICS:
        engine.register(metric_cls())
    return engine


class TestCanonicalItemInvariant:
    """Structural invariants on the canonical fixture set."""

    def test_has_eight_items(self) -> None:
        assert len(CANONICAL_ITEMS) == 8

    def test_unique_keys(self) -> None:
        keys = [item.key for item in CANONICAL_ITEMS]
        assert len(keys) == len(set(keys))

    def test_all_have_prompt(self) -> None:
        for item in CANONICAL_ITEMS:
            assert item.prompt, f"{item.key} has empty prompt"

    def test_all_have_response(self) -> None:
        for item in CANONICAL_ITEMS:
            assert item.response, f"{item.key} has empty response"

    def test_correct_answer_exists(self) -> None:
        item = get_item("correct_answer")
        assert "Paris" in item.response

    def test_incorrect_answer_exists(self) -> None:
        item = get_item("incorrect_answer")
        assert "Berlin" in item.response

    def test_irrelevant_answer_exists(self) -> None:
        item = get_item("irrelevant_answer")
        assert "apple pie" in item.response

    def test_hallucinated_answer_has_fabrication(self) -> None:
        item = get_item("hallucinated_answer")
        assert "12 million" in item.response
        assert item.context

    def test_context_grounded_supported(self) -> None:
        item = get_item("context_grounded")
        assert "solar" in item.response.lower()

    def test_ungrounded_unsupported(self) -> None:
        item = get_item("ungrounded")
        assert "lunar" in item.response.lower()


class TestGoldenDeterministicMetrics:
    """Golden tests for deterministic metrics with exact expected values."""

    def test_json_validity_correct_answer_not_json(self) -> None:
        from app.evaluation.metrics.implementations.json_validity_metric import (
            JsonValidityMetric,
        )

        metric = JsonValidityMetric()
        item = get_item("correct_answer")
        result = _evaluate_sync(metric, MetricInput(response=item.response))
        assert result.is_success
        assert result.normalized_score == 0.0

    def test_json_validity_invalid_structured(self) -> None:
        from app.evaluation.metrics.implementations.json_validity_metric import (
            JsonValidityMetric,
        )

        metric = JsonValidityMetric()
        item = get_item("invalid_structured")
        result = _evaluate_sync(metric, MetricInput(response=item.response))
        assert result.is_success
        assert result.normalized_score == 1.0  # valid JSON

    def test_json_validity_non_json(self) -> None:
        from app.evaluation.metrics.implementations.json_validity_metric import (
            JsonValidityMetric,
        )

        metric = JsonValidityMetric()
        result = _evaluate_sync(metric, MetricInput(response="not json"))
        assert result.is_success
        assert result.normalized_score == 0.0

    def test_schema_valid_structured(self) -> None:
        from app.evaluation.metrics.implementations.schema_validation_metric import (
            SchemaValidationMetric,
        )

        metric = SchemaValidationMetric()
        item = get_item("valid_structured")
        result = _evaluate_sync(
            metric,
            MetricInput(
                response=item.response,
                metadata={"schema": item.schema},
            ),
        )
        assert result.is_success
        assert result.normalized_score == 1.0

    def test_schema_invalid_structured(self) -> None:
        from app.evaluation.metrics.implementations.schema_validation_metric import (
            SchemaValidationMetric,
        )

        metric = SchemaValidationMetric()
        item = get_item("invalid_structured")
        result = _evaluate_sync(
            metric,
            MetricInput(
                response=item.response,
                metadata={"schema": item.schema},
            ),
        )
        assert result.is_success
        assert result.normalized_score == 0.0

    def test_response_length_nonempty(self) -> None:
        from app.evaluation.metrics.implementations.response_length_metric import (
            ResponseLengthMetric,
        )

        metric = ResponseLengthMetric()
        item = get_item("correct_answer")
        result = _evaluate_sync(metric, MetricInput(response=item.response))
        assert result.is_success
        assert result.normalized_score > 0.0

    def test_regex_validation_match(self) -> None:
        from app.evaluation.metrics.implementations.regex_validation_metric import (
            RegexValidationMetric,
        )

        metric = RegexValidationMetric()
        result = _evaluate_sync(
            metric,
            MetricInput(response="The capital is Paris", metadata={"regex_pattern": r"Paris"}),
        )
        assert result.is_success
        assert result.normalized_score == 1.0

    def test_regex_validation_no_match(self) -> None:
        from app.evaluation.metrics.implementations.regex_validation_metric import (
            RegexValidationMetric,
        )

        metric = RegexValidationMetric()
        result = _evaluate_sync(
            metric,
            MetricInput(response="The capital is Berlin", metadata={"regex_pattern": r"Paris"}),
        )
        assert result.is_success
        assert result.normalized_score == 0.0

    def test_tool_call_correctness_valid(self) -> None:
        from app.evaluation.metrics.implementations.tool_call_correctness_metric import (
            ToolCallCorrectnessMetric,
        )

        metric = ToolCallCorrectnessMetric()
        result = _evaluate_sync(
            metric,
            MetricInput(
                prompt="use tools",
                response="calling tool",
                tool_calls=({"name": "search", "arguments": "{}"},),
            ),
        )
        assert result.is_success
        assert result.normalized_score == 1.0

    def test_token_usage_in_range(self) -> None:
        from app.evaluation.metrics.implementations.token_usage_metric import TokenUsageMetric

        metric = TokenUsageMetric()
        result = _evaluate_sync(
            metric,
            MetricInput(metadata={"tokens_input": 100, "tokens_output": 50}),
        )
        assert result.is_success
        assert 0.0 <= result.normalized_score <= 1.0

    def test_cost_in_range(self) -> None:
        from app.evaluation.metrics.implementations.cost_metric import CostMetric

        metric = CostMetric()
        result = _evaluate_sync(metric, MetricInput(metadata={"cost_usd": 0.05}))
        assert result.is_success
        assert 0.0 <= result.normalized_score <= 1.0

    def test_latency_in_range(self) -> None:
        from app.evaluation.metrics.implementations.latency_metric import LatencyMetric

        metric = LatencyMetric()
        result = _evaluate_sync(metric, MetricInput(metadata={"latency_ms": 1000.0}))
        assert result.is_success
        assert 0.0 <= result.normalized_score <= 1.0


class TestGoldenEmbeddingMetrics:
    """Golden tests for embedding metrics with deterministic provider."""

    def test_semantic_similarity_identical(self) -> None:
        from app.evaluation.metrics.implementations.semantic_similarity_metric import (
            SemanticSimilarityMetric,
        )

        provider = DeterministicEmbeddingProvider()
        metric = SemanticSimilarityMetric()
        result = _evaluate_sync(
            metric,
            MetricInput(
                response="Paris is the capital of France",
                reference="Paris is the capital of France",
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(1.0, abs=0.01)

    def test_groundedness_context_match(self) -> None:
        from app.evaluation.metrics.implementations.groundedness_metric import (
            GroundednessMetric,
        )

        provider = DeterministicEmbeddingProvider()
        metric = GroundednessMetric()
        item = get_item("context_grounded")
        result = _evaluate_sync(
            metric,
            MetricInput(
                response=item.response,
                context=item.context,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score > 0.0


class TestGoldenJudgeMetrics:
    """Golden tests for judge metrics with scripted provider."""

    def test_correctness_with_scripted_judge(self) -> None:
        from app.evaluation.metrics.implementations.correctness_metric import (
            CorrectnessMetric,
        )

        provider = ScriptedJudgeProvider(score=0.9, confidence=0.95)
        metric = CorrectnessMetric()
        result = _evaluate_sync(
            metric,
            MetricInput(
                prompt="What is the capital of France?",
                response="Paris",
                reference="Paris",
                metadata={"_judge_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(0.9, abs=0.01)

    def test_coherence_with_scripted_judge(self) -> None:
        from app.evaluation.metrics.implementations.coherence_metric import CoherenceMetric

        provider = ScriptedJudgeProvider(score=0.8, confidence=0.85)
        metric = CoherenceMetric()
        result = _evaluate_sync(
            metric,
            MetricInput(
                prompt="Explain gravity",
                response="Gravity pulls objects together.",
                metadata={"_judge_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(0.8, abs=0.01)


def _evaluate_sync(metric: object, input_data: MetricInput) -> MetricResult:
    """Synchronously evaluate a metric for test convenience."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(metric.evaluate(input_data))
    finally:
        loop.close()
