"""Score-contract enforcement tests for all registered metrics.

Every metric must honor the MetricResult contract documented in
``app.evaluation.metrics.domain.MetricResult``:

- successful results carry ``normalized_score`` in [0.0, 1.0] and a
  ``version`` equal to their definition version;
- every failure path produces an explicit error result
  (``is_success`` False) instead of a silent zero score;
- definitions declare directionality and an optional default
  threshold within [0.0, 1.0].
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from app.evaluation.metrics.domain import (
    MetricAggregation,
    MetricCategory,
    MetricInput,
    MetricResult,
    MetricScale,
    ScoreDirection,
)
from app.evaluation.metrics.implementations import ALL_METRICS
from app.evaluation.metrics.implementations.embedding_base import EmbeddingMetric
from app.evaluation.metrics.implementations.llm_judge_base import LLMJudgeMetric
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, EmbeddingResponse, Usage

_EMBEDDING_DIMS = 8


class DeterministicEmbeddingProvider:
    """Fake embedding provider mapping text to stable hash-derived vectors.

    Identical texts always produce identical vectors; different texts
    produce different (near-orthogonal on average) vectors. No network,
    no randomness, no fabricated similarity structure beyond hashing.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    provider_name = "deterministic-embeddings"

    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
        options: Any = None,
    ) -> EmbeddingResponse:
        self.calls.extend(texts)
        vector = tuple(
            (b - 127.5) / 127.5
            for b in hashlib.sha256(
                texts[0].encode("utf-8"),
            ).digest()[:_EMBEDDING_DIMS]
        )
        return EmbeddingResponse(
            model=model,
            provider="deterministic-test",
            usage=Usage(),
            finish_reason=FinishReason.STOP,
            embedding=vector,
            dimensions=len(vector),
        )


class ScriptedJudgeProvider:
    """Fake chat provider returning a fixed structured judge verdict."""

    provider_name = "scripted-judge"

    def __init__(
        self,
        score: float = 0.75,
        confidence: float = 0.9,
        reasoning: str = "scripted verdict",
    ) -> None:
        self._payload = {
            "score": score,
            "confidence": confidence,
            "reasoning": reasoning,
        }

    async def chat(
        self,
        messages: list[Any],
        *,
        model: str,
        options: Any = None,
    ) -> ChatResponse:
        return ChatResponse(
            content=json.dumps(self._payload),
            model=model,
            provider="scripted-test",
            usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
            finish_reason=FinishReason.STOP,
        )


def _canonical_input(metric_name: str) -> MetricInput | None:
    """Build a minimal input that lets the metric compute successfully."""
    embedding_provider = DeterministicEmbeddingProvider()
    judge_provider = ScriptedJudgeProvider()
    base_meta: dict[str, Any] = {}

    embedding_inputs: dict[str, MetricInput] = {
        "semantic_similarity": MetricInput(
            response="Paris is the capital of France",
            reference="The capital of France is Paris",
            metadata={"_embedding_provider": embedding_provider},
        ),
        "answer_relevance": MetricInput(
            prompt="What is the capital of France?",
            response="Paris is the capital of France",
            metadata={"_embedding_provider": embedding_provider},
        ),
        "groundedness": MetricInput(
            response="Paris is the capital of France",
            context="France is a country in Europe. Its capital is Paris.",
            metadata={"_embedding_provider": embedding_provider},
        ),
        "context_relevance": MetricInput(
            prompt="What is the capital of France?",
            context="France is a country in Europe. Its capital is Paris.",
            metadata={"_embedding_provider": embedding_provider},
        ),
    }
    if metric_name in embedding_inputs:
        return embedding_inputs[metric_name]

    judge_requirements: dict[str, dict[str, str]] = {
        "correctness": {"reference": "Paris"},
        "faithfulness": {"context": "Paris is the capital of France."},
        "hallucination": {"context": "Paris is the capital of France."},
    }
    if metric_name in judge_requirements:
        base_meta["_judge_provider"] = judge_provider
        return MetricInput(
            prompt="What is the capital of France?",
            response="Paris is the capital of France",
            **{**judge_requirements[metric_name], "metadata": base_meta},
        )
    if metric_name in {
        "coherence",
        "bias",
        "toxicity",
        "safety",
        "instruction_following",
        "reasoning_quality",
        "prompt_injection",
        "jailbreak",
    }:
        return MetricInput(
            prompt="What is the capital of France?",
            response="Paris is the capital of France",
            metadata={"_judge_provider": judge_provider},
        )

    deterministic_inputs: dict[str, MetricInput] = {
        "json_validity": MetricInput(response='{"capital": "Paris"}'),
        "schema_validation": MetricInput(
            response='{"capital": "Paris"}',
            metadata={"schema": {"type": "object"}},
        ),
        "regex_validation": MetricInput(
            response="The capital is Paris",
            metadata={"regex_pattern": r"Paris"},
        ),
        "response_length": MetricInput(response="Paris is the capital of France"),
        "tool_call_correctness": MetricInput(
            prompt="use tools",
            response="calling tool",
            tool_calls=({"name": "search", "arguments": "{}"},),
        ),
        "token_usage": MetricInput(
            prompt="hi",
            response="hello",
            metadata={"tokens_input": 3, "tokens_output": 2},
        ),
        "cost": MetricInput(
            prompt="hi",
            response="hello",
            metadata={"cost_usd": 0.01},
        ),
        "latency": MetricInput(
            prompt="hi",
            response="hello",
            metadata={"latency_ms": 250.0},
        ),
    }
    return deterministic_inputs.get(metric_name)


def _failing_input(metric_name: str) -> MetricInput:
    """Build an input that violates the metric's input requirements."""
    return {
        "semantic_similarity": MetricInput(response="orphan response"),
        "answer_relevance": MetricInput(prompt="only a prompt"),
        "groundedness": MetricInput(response="response without context"),
        "context_relevance": MetricInput(prompt="prompt without context"),
        "correctness": MetricInput(response="no reference given"),
        "faithfulness": MetricInput(response="no context given"),
        "hallucination": MetricInput(response="no context given"),
        "coherence": MetricInput(prompt="p"),
        "bias": MetricInput(prompt="p"),
        "toxicity": MetricInput(prompt="p"),
        "safety": MetricInput(prompt="p"),
        "prompt_injection": MetricInput(prompt="p"),
        "jailbreak": MetricInput(prompt="p"),
        "instruction_following": MetricInput(prompt="p"),
        "reasoning_quality": MetricInput(prompt="p"),
        "json_validity": MetricInput(),
        "schema_validation": MetricInput(response='{"a": 1}'),
        "regex_validation": MetricInput(response="no pattern configured"),
        "response_length": MetricInput(),
        "tool_call_correctness": MetricInput(),
        "token_usage": MetricInput(metadata={}),
        "cost": MetricInput(metadata={}),
        "latency": MetricInput(metadata={}),
    }[metric_name]


class TestDefinitionContract:
    """Static contract checks on every registered metric definition."""

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_definition_declares_contract_fields(self, metric_cls: type) -> None:
        definition = metric_cls().definition()

        assert definition.name
        assert definition.version
        assert isinstance(definition.category, MetricCategory)
        assert isinstance(definition.scale, MetricScale)
        assert isinstance(definition.direction, ScoreDirection)

        if definition.default_threshold is not None:
            assert 0.0 <= definition.default_threshold <= 1.0

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_lower_is_better_only_for_perf_cost(self, metric_cls: type) -> None:
        definition = metric_cls().definition()

        if definition.direction is ScoreDirection.LOWER_IS_BETTER:
            assert definition.category in {
                MetricCategory.PERFORMANCE,
                MetricCategory.COST,
            }


class TestResultContract:
    """Runtime contract checks on results from every registered metric."""

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    @pytest.mark.asyncio
    async def test_happy_path_result_honors_contract(self, metric_cls: type) -> None:
        metric = metric_cls()
        definition = metric.definition()
        input_data = _canonical_input(definition.name)

        assert input_data is not None, f"no canonical input for {definition.name}"

        result = await metric.evaluate(input_data)

        assert result.metric_name == definition.name
        assert result.is_success, f"{definition.name} failed: {result.error}"
        assert result.is_valid_score
        assert result.version == definition.version
        assert result.error is None
        assert result.execution_time_ms >= 0

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    @pytest.mark.asyncio
    async def test_execution_metadata_records_provenance(
        self,
        metric_cls: type,
    ) -> None:
        metric = metric_cls()
        definition = metric.definition()
        input_data = _canonical_input(definition.name)

        assert input_data is not None

        result = await metric.evaluate(input_data)

        assert result.is_success, f"{definition.name} failed: {result.error}"
        metadata = result.metadata

        if isinstance(metric, LLMJudgeMetric):
            assert "judge_model" in metadata
            assert "judge_prompt_version" in metadata
            assert "rubric_version" in metadata
            assert "provider" in metadata
            assert metadata["provider"]
        elif isinstance(metric, EmbeddingMetric):
            assert metadata.get("embedding_model")
            assert "embedding_provider" in metadata

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    @pytest.mark.asyncio
    async def test_missing_inputs_produce_explicit_errors(
        self,
        metric_cls: type,
    ) -> None:
        metric = metric_cls()
        definition = metric.definition()

        result = await metric.evaluate(_failing_input(definition.name))

        assert not result.is_success, (
            f"{definition.name} returned a silent zero instead of an error"
        )
        assert result.error


class TestAggregationExcludesErrors:
    """Errored results must never contaminate aggregated scores."""

    @pytest.mark.asyncio
    async def test_error_results_excluded_from_mean(self) -> None:
        good = MetricResult(
            metric_name="m",
            score=0.8,
            normalized_score=0.8,
        )
        errored = MetricResult(
            metric_name="m",
            score=0.0,
            normalized_score=0.0,
            error="provider unavailable",
        )
        aggregation = MetricAggregation.from_results("m", (good, errored))

        assert aggregation.success_count == 1
        assert aggregation.error_count == 1
        assert aggregation.mean == pytest.approx(0.8)


class TestPassedAgainst:
    """Threshold semantics on MetricResult."""

    def test_none_threshold_returns_none(self) -> None:
        result = MetricResult(metric_name="m", score=1.0, normalized_score=1.0)
        assert result.passed_against(None) is None

    def test_error_result_returns_none_even_with_threshold(self) -> None:
        result = MetricResult(
            metric_name="m",
            score=0.0,
            normalized_score=0.0,
            error="boom",
        )
        assert result.passed_against(0.5) is None

    @pytest.mark.parametrize(
        ("normalized", "threshold", "expected"),
        [
            (0.9, 0.5, True),
            (0.5, 0.5, True),
            (0.49, 0.5, False),
            (0.0, 0.0, True),
        ],
    )
    def test_threshold_comparison_is_inclusive(
        self,
        normalized: float,
        threshold: float,
        expected: bool,
    ) -> None:
        result = MetricResult(
            metric_name="m",
            score=normalized,
            normalized_score=normalized,
        )
        assert result.passed_against(threshold) is expected
