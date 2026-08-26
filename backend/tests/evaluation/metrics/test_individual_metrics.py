"""Known-answer tests for individual metric implementations.

Every assertion below has a hand-computable expected value:
embedding metrics run against scripted vectors (identical -> 1.0,
orthogonal -> 0.0, 45 degrees -> 1/sqrt(2)), judge metrics against
scripted verdicts, and deterministic metrics against exact math.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.evaluation.metrics.domain import MetricCategory, MetricInput, MetricScale
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.metrics.implementations.cost_metric import CostMetric
from app.evaluation.metrics.implementations.json_validity_metric import JsonValidityMetric
from app.evaluation.metrics.implementations.latency_metric import LatencyMetric
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric
from app.evaluation.metrics.implementations.regex_validation_metric import (
    RegexValidationMetric,
)
from app.evaluation.metrics.implementations.response_length_metric import (
    ResponseLengthMetric,
)
from app.evaluation.metrics.implementations.schema_validation_metric import (
    SchemaValidationMetric,
)
from app.evaluation.metrics.implementations.semantic_similarity_metric import (
    SemanticSimilarityMetric,
)
from app.evaluation.metrics.implementations.token_usage_metric import TokenUsageMetric
from app.evaluation.metrics.implementations.tool_call_correctness_metric import (
    ToolCallCorrectnessMetric,
)
from tests.evaluation.metrics.fakes import (
    ALPHA,
    BETA,
    DELTA,
    GAMMA,
    ScriptedEmbeddingProvider,
    ScriptedJudgeProvider,
)

JUDGE_METRICS = [m for m in ALL_METRICS if issubclass(m, LLMJudgeMetric)]


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


class TestSemanticSimilarityKnownAnswers:
    """Cosine similarity must reproduce exact trigonometric values."""

    @pytest.mark.asyncio
    async def test_identical_texts_score_one(self) -> None:
        provider = ScriptedEmbeddingProvider()
        result = await SemanticSimilarityMetric().evaluate(
            MetricInput(
                response=GAMMA,
                reference=GAMMA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_orthogonal_texts_score_zero(self) -> None:
        provider = ScriptedEmbeddingProvider()
        result = await SemanticSimilarityMetric().evaluate(
            MetricInput(
                response=ALPHA,
                reference=BETA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_45_degree_angle_scores_inverse_sqrt_two(self) -> None:
        provider = ScriptedEmbeddingProvider()
        result = await SemanticSimilarityMetric().evaluate(
            MetricInput(
                response=GAMMA,
                reference=DELTA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(1.0 / math.sqrt(2))

    @pytest.mark.asyncio
    async def test_embedding_model_recorded(self) -> None:
        provider = ScriptedEmbeddingProvider(model="emb-x")
        result = await SemanticSimilarityMetric().evaluate(
            MetricInput(
                response=GAMMA,
                reference=GAMMA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.metadata["embedding_model"] == "emb-x"
        assert result.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_missing_reference_is_error(self) -> None:
        result = await SemanticSimilarityMetric().evaluate(
            MetricInput(response=GAMMA),
        )
        assert not result.is_success


class TestPromptResponseEmbeddingMetrics:
    """answer_relevance measures prompt/response cosine."""

    @pytest.mark.asyncio
    async def test_identical_prompt_response_scores_one(self) -> None:
        from app.evaluation.metrics.implementations.answer_relevance_metric import (
            AnswerRelevanceMetric,
        )

        metric = AnswerRelevanceMetric()
        provider = ScriptedEmbeddingProvider()
        result = await metric.evaluate(
            MetricInput(
                prompt=GAMMA,
                response=GAMMA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(1.0)
        assert result.metadata["embedding_model"] == "text-embedding-test"

    @pytest.mark.asyncio
    async def test_orthogonal_pair_scores_zero(self) -> None:
        from app.evaluation.metrics.implementations.answer_relevance_metric import (
            AnswerRelevanceMetric,
        )

        metric = AnswerRelevanceMetric()
        provider = ScriptedEmbeddingProvider()
        result = await metric.evaluate(
            MetricInput(
                prompt=ALPHA,
                response=BETA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(0.0)


class TestGroundednessKnownAnswers:
    """Groundedness is cosine(response, context)."""

    @pytest.mark.asyncio
    async def test_identical_text_scores_one(self) -> None:
        from app.evaluation.metrics.implementations.groundedness_metric import (
            GroundednessMetric,
        )

        provider = ScriptedEmbeddingProvider()
        result = await GroundednessMetric().evaluate(
            MetricInput(
                response=GAMMA,
                context=GAMMA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_unrelated_text_scores_zero(self) -> None:
        from app.evaluation.metrics.implementations.groundedness_metric import (
            GroundednessMetric,
        )

        provider = ScriptedEmbeddingProvider()
        result = await GroundednessMetric().evaluate(
            MetricInput(
                response=ALPHA,
                context=BETA,
                metadata={"_embedding_provider": provider},
            ),
        )
        assert result.is_success
        assert result.normalized_score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_missing_context_is_error(self) -> None:
        from app.evaluation.metrics.implementations.groundedness_metric import (
            GroundednessMetric,
        )

        result = await GroundednessMetric().evaluate(MetricInput(response=GAMMA))
        assert not result.is_success


class TestJudgeMetricsKnownAnswers:
    """Judge metrics propagate scripted verdicts exactly."""

    @pytest.mark.parametrize("metric_cls", JUDGE_METRICS)
    @pytest.mark.asyncio
    async def test_verdict_score_propagates(self, metric_cls: type) -> None:
        provider = ScriptedJudgeProvider({"score": 0.25, "confidence": 0.5, "reasoning": "r"})
        metric = metric_cls()
        input_data = _judge_input(metric.definition().name, provider)

        result = await metric.evaluate(input_data)

        assert result.is_success, f"{metric.definition().name}: {result.error}"
        assert result.normalized_score == pytest.approx(0.25)
        assert result.score == pytest.approx(0.25)
        assert result.confidence == pytest.approx(0.5)
        assert result.reasoning == "r"
        assert result.metadata["judge_model"] == "judge-model"
        assert result.metadata["rubric_version"]
        assert result.metadata["judge_prompt_version"]
        assert result.metadata["tokens_input"] == 20
        assert result.metadata["tokens_output"] == 10
        assert result.version == metric.definition().version

    @pytest.mark.parametrize("metric_cls", JUDGE_METRICS)
    @pytest.mark.asyncio
    async def test_malformed_verdict_is_explicit_error(self, metric_cls: type) -> None:
        provider = ScriptedJudgeProvider("Score: 0.9 because I said so")
        metric = metric_cls()

        result = await metric.evaluate(_judge_input(metric.definition().name, provider))

        assert not result.is_success
        assert result.error

    @pytest.mark.parametrize("metric_cls", JUDGE_METRICS)
    @pytest.mark.asyncio
    async def test_provider_failure_is_explicit_error(self, metric_cls: type) -> None:
        provider = ScriptedJudgeProvider(RuntimeError("provider down"))
        metric = metric_cls()

        result = await metric.evaluate(_judge_input(metric.definition().name, provider))

        assert not result.is_success
        assert result.error
        assert "provider down" in (result.error or "")


def _judge_input(metric_name: str, provider: Any) -> MetricInput:
    """Build valid input for a judge metric based on its requirements."""
    metadata: dict[str, Any] = {"_judge_provider": provider}
    kwargs: dict[str, Any] = {
        "prompt": "What is the capital of France?",
        "response": "Paris is the capital of France.",
        "metadata": metadata,
    }
    if metric_name == "correctness":
        kwargs["reference"] = "Paris"
    if metric_name in {"faithfulness", "hallucination"}:
        kwargs["context"] = "Paris is the capital of France."
    return MetricInput(**kwargs)


class TestDeterministicMetricsExactMath:
    """Cost/perf/length metrics follow exact formulas on known inputs."""

    @pytest.mark.asyncio
    async def test_token_usage_exact_ratios(self) -> None:
        metric = TokenUsageMetric()
        half = await metric.evaluate(MetricInput(metadata={"tokens_output": 2048}))
        quarter = await metric.evaluate(MetricInput(metadata={"tokens_output": 1024}))
        full = await metric.evaluate(MetricInput(metadata={"tokens_output": 4096}))

        assert half.normalized_score == pytest.approx(0.5)
        assert quarter.normalized_score == pytest.approx(0.75)
        assert full.normalized_score == pytest.approx(0.0)
        assert quarter.score == 1024.0

    @pytest.mark.asyncio
    async def test_latency_at_threshold_scores_zero(self) -> None:
        metric = LatencyMetric()
        at_threshold = await metric.evaluate(
            MetricInput(metadata={"latency_ms": metric.DEFAULT_THRESHOLD_MS}),
        )
        fast = await metric.evaluate(MetricInput(metadata={"latency_ms": 50}))
        slow = await metric.evaluate(MetricInput(metadata={"latency_ms": 100000}))

        assert at_threshold.normalized_score == pytest.approx(0.0)
        assert fast.normalized_score > slow.normalized_score
        assert fast.normalized_score < 1.0
        assert at_threshold.score == float(metric.DEFAULT_THRESHOLD_MS)

    @pytest.mark.asyncio
    async def test_cost_at_cap_scores_zero_and_free_is_perfect(self) -> None:
        metric = CostMetric()
        at_cap = await metric.evaluate(
            MetricInput(metadata={"cost_usd": metric.DEFAULT_MAX_COST_USD}),
        )
        free = await metric.evaluate(MetricInput(metadata={"cost_usd": 0.0}))
        cheap = await metric.evaluate(MetricInput(metadata={"cost_usd": 0.001}))

        assert at_cap.normalized_score == pytest.approx(0.0)
        assert free.normalized_score == pytest.approx(1.0)
        assert cheap.normalized_score > at_cap.normalized_score
        assert cheap.cost_usd == 0.001

    @pytest.mark.asyncio
    async def test_response_length_triangle_profile(self) -> None:
        metric = ResponseLengthMetric()
        bounds = {"expected_min_length": 0, "expected_max_length": 100}

        at_mid = await metric.evaluate(
            MetricInput(response="x" * 50, metadata=bounds),
        )
        at_edge = await metric.evaluate(
            MetricInput(response="x" * 100, metadata=bounds),
        )

        assert at_mid.normalized_score == pytest.approx(1.0)
        assert at_edge.normalized_score == pytest.approx(0.0)
        assert at_mid.metadata["char_count"] == 50

    @pytest.mark.asyncio
    async def test_word_count_target(self) -> None:
        metric = ResponseLengthMetric()
        on_target = await metric.evaluate(
            MetricInput(response="one two three", metadata={"expected_word_count": 3}),
        )
        off_target = await metric.evaluate(
            MetricInput(response="one two three four five", metadata={"expected_word_count": 3}),
        )

        assert on_target.normalized_score == pytest.approx(1.0)
        assert off_target.normalized_score == pytest.approx(1.0 - abs(1.0 - 5 / 3))


class TestValidationMetrics:
    """Binary validation metrics with explicit pass/fail answers."""

    @pytest.mark.asyncio
    async def test_json_validity(self) -> None:
        metric = JsonValidityMetric()
        valid = await metric.evaluate(MetricInput(response='{"a": [1, 2]}'))
        invalid = await metric.evaluate(MetricInput(response="{not json"))
        primitive = await metric.evaluate(MetricInput(response='"just a string"'))

        assert valid.normalized_score == 1.0
        assert invalid.normalized_score == 0.0
        assert primitive.normalized_score == 0.0

    @pytest.mark.asyncio
    async def test_regex_validation(self) -> None:
        metric = RegexValidationMetric()
        match = await metric.evaluate(
            MetricInput(response="Order #12345 shipped", metadata={"regex_pattern": r"#\d+"}),
        )
        no_match = await metric.evaluate(
            MetricInput(response="no number here", metadata={"regex_pattern": r"#\d+"}),
        )
        missing_pattern = await metric.evaluate(MetricInput(response="anything"))

        assert match.normalized_score == 1.0
        assert no_match.normalized_score == 0.0
        assert not missing_pattern.is_success

    @pytest.mark.asyncio
    async def test_schema_validation(self) -> None:
        metric = SchemaValidationMetric()
        schema = {"type": "object", "required": ["answer"]}

        conforms = await metric.evaluate(
            MetricInput(response='{"answer": 42}', metadata={"schema": schema}),
        )
        violates = await metric.evaluate(
            MetricInput(response='{"other": 1}', metadata={"schema": schema}),
        )
        not_json = await metric.evaluate(
            MetricInput(response="plain text", metadata={"schema": schema}),
        )
        missing_schema = await metric.evaluate(MetricInput(response='{"answer": 42}'))

        assert conforms.normalized_score == 1.0
        assert violates.normalized_score == 0.0
        assert not_json.normalized_score == 0.0
        assert not missing_schema.is_success

    @pytest.mark.asyncio
    async def test_tool_call_correctness(self) -> None:
        metric = ToolCallCorrectnessMetric()
        valid = await metric.evaluate(
            MetricInput(tool_calls=({"name": "search", "arguments": {"q": "x"}},)),
        )
        json_string_args = await metric.evaluate(
            MetricInput(tool_calls=({"name": "search", "arguments": '{"q": "x"}'},)),
        )
        invalid = await metric.evaluate(
            MetricInput(tool_calls=({"arguments": {"q": "x"}},)),
        )
        missing_data = await metric.evaluate(MetricInput())

        assert valid.normalized_score == 1.0
        assert json_string_args.normalized_score == 1.0
        assert invalid.normalized_score == 0.0
        assert not missing_data.is_success
