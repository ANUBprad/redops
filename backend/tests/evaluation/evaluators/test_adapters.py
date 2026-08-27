"""Tests for the evaluator adapter layer.

Covers BaseEvaluatorAdapter, EvaluatorRegistry, and all five
built-in adapter implementations (Heuristic, Embedding, LLMJudge,
RAGAS, Custom).
"""

from __future__ import annotations

import pytest

from app.evaluation.evaluators.adapters import (
    CustomAdapter,
    EmbeddingAdapter,
    HeuristicAdapter,
    LLMJudgeAdapter,
    RAGASAdapter,
)
from app.evaluation.evaluators.base import (
    EvaluatorConfig,
    EvaluatorRegistry,
)
from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricInput,
    MetricResult,
)


class TestHeuristicAdapter:
    """Tests for HeuristicAdapter."""

    def test_evaluator_type(self) -> None:
        adapter = HeuristicAdapter()
        assert adapter.evaluator_type() == EvaluatorType.HEURISTIC

    def test_supports_all_metrics(self) -> None:
        adapter = HeuristicAdapter()
        assert adapter.supports_metric("any_metric") is True

    @pytest.mark.asyncio
    async def test_evaluate_raises_not_implemented(self) -> None:
        adapter = HeuristicAdapter()
        input_data = MetricInput(prompt="test", response="test")
        with pytest.raises(NotImplementedError, match="HeuristicAdapter"):
            await adapter.evaluate("test_metric", input_data)

    @pytest.mark.asyncio
    async def test_initialize_and_shutdown_are_noop(self) -> None:
        adapter = HeuristicAdapter()
        await adapter.initialize()
        await adapter.shutdown()


class TestEmbeddingAdapter:
    """Tests for EmbeddingAdapter."""

    def test_evaluator_type(self) -> None:
        adapter = EmbeddingAdapter()
        assert adapter.evaluator_type() == EvaluatorType.EMBEDDING

    @pytest.mark.asyncio
    async def test_evaluate_raises_not_implemented(self) -> None:
        adapter = EmbeddingAdapter()
        input_data = MetricInput(prompt="test", response="test")
        with pytest.raises(NotImplementedError, match="EmbeddingAdapter"):
            await adapter.evaluate("test_metric", input_data)


class TestLLMJudgeAdapter:
    """Tests for LLMJudgeAdapter."""

    def test_evaluator_type(self) -> None:
        adapter = LLMJudgeAdapter()
        assert adapter.evaluator_type() == EvaluatorType.LLM_JUDGE

    @pytest.mark.asyncio
    async def test_evaluate_raises_not_implemented(self) -> None:
        adapter = LLMJudgeAdapter()
        input_data = MetricInput(prompt="test", response="test")
        with pytest.raises(NotImplementedError, match="LLMJudgeAdapter"):
            await adapter.evaluate("test_metric", input_data)


class TestRAGASAdapter:
    """Tests for RAGASAdapter."""

    def test_evaluator_type(self) -> None:
        adapter = RAGASAdapter()
        assert adapter.evaluator_type() == EvaluatorType.RAGAS

    @pytest.mark.asyncio
    async def test_evaluate_without_ragas_installed(self) -> None:
        adapter = RAGASAdapter()
        input_data = MetricInput(prompt="test", response="test")
        result = await adapter.evaluate("faithfulness", input_data)
        assert result.score == 0.0
        assert result.error is not None
        assert "ragas" in result.error.lower()

    @pytest.mark.asyncio
    async def test_evaluate_unsupported_metric_name(self) -> None:
        adapter = RAGASAdapter()
        input_data = MetricInput(prompt="test", response="test")
        result = await adapter.evaluate("nonexistent_ragas_metric", input_data)
        assert result.score == 0.0
        assert result.error is not None


class TestCustomAdapter:
    """Tests for CustomAdapter."""

    def test_evaluator_type(self) -> None:
        adapter = CustomAdapter()
        assert adapter.evaluator_type() == EvaluatorType.CUSTOM

    @pytest.mark.asyncio
    async def test_evaluate_no_evaluator_registered(self) -> None:
        adapter = CustomAdapter()
        input_data = MetricInput(prompt="test", response="test")
        result = await adapter.evaluate("unregistered_metric", input_data)
        assert result.score == 0.0
        assert result.error is not None
        assert "No custom evaluator" in result.error

    @pytest.mark.asyncio
    async def test_evaluate_with_registered_evaluator(self) -> None:
        adapter = CustomAdapter()

        async def my_evaluator(
            input_data: MetricInput,
            config: EvaluatorConfig | None,
        ) -> MetricResult:
            return MetricResult(
                metric_name="my_metric",
                score=0.95,
                normalized_score=0.95,
            )

        adapter.register_evaluator("my_metric", my_evaluator)
        input_data = MetricInput(prompt="test", response="test")
        result = await adapter.evaluate("my_metric", input_data)
        assert result.score == 0.95
        assert result.is_success

    @pytest.mark.asyncio
    async def test_evaluate_evaluator_exception(self) -> None:
        adapter = CustomAdapter()

        async def failing_evaluator(
            input_data: MetricInput,
            config: EvaluatorConfig | None,
        ) -> MetricResult:
            raise ValueError("boom")

        adapter.register_evaluator("fail_metric", failing_evaluator)
        input_data = MetricInput(prompt="test", response="test")
        result = await adapter.evaluate("fail_metric", input_data)
        assert result.score == 0.0
        assert result.error is not None
        assert "Custom evaluator failed" in result.error


class TestEvaluatorRegistry:
    """Tests for the EvaluatorRegistry dispatcher."""

    def test_empty_registry(self) -> None:
        registry = EvaluatorRegistry()
        assert registry.get(EvaluatorType.HEURISTIC) is None
        assert registry.list_types() == []

    def test_register_and_get(self) -> None:
        registry = EvaluatorRegistry()
        adapter = HeuristicAdapter()
        registry.register(adapter)
        assert registry.get(EvaluatorType.HEURISTIC) is adapter
        assert registry.has_adapter(EvaluatorType.HEURISTIC)

    def test_get_or_fallback_found(self) -> None:
        registry = EvaluatorRegistry()
        heuristic = HeuristicAdapter()
        registry.register(heuristic)
        result = registry.get_or_fallback(EvaluatorType.HEURISTIC)
        assert result is heuristic

    def test_get_or_fallback_uses_fallback(self) -> None:
        registry = EvaluatorRegistry()
        heuristic = HeuristicAdapter()
        registry.register(heuristic, as_fallback=True)
        result = registry.get_or_fallback(EvaluatorType.LLM_JUDGE)
        assert result is heuristic

    def test_get_or_fallback_no_fallback(self) -> None:
        registry = EvaluatorRegistry()
        result = registry.get_or_fallback(EvaluatorType.LLM_JUDGE)
        assert result is None

    def test_list_types(self) -> None:
        registry = EvaluatorRegistry()
        registry.register(HeuristicAdapter())
        registry.register(EmbeddingAdapter())
        types = registry.list_types()
        assert len(types) == 2
        assert EvaluatorType.HEURISTIC in types
        assert EvaluatorType.EMBEDDING in types

    @pytest.mark.asyncio
    async def test_initialize_all(self) -> None:
        registry = EvaluatorRegistry()
        registry.register(HeuristicAdapter())
        registry.register(EmbeddingAdapter())
        await registry.initialize_all()

    @pytest.mark.asyncio
    async def test_shutdown_all(self) -> None:
        registry = EvaluatorRegistry()
        registry.register(HeuristicAdapter())
        await registry.shutdown_all()


class TestEvaluatorConfig:
    """Tests for EvaluatorConfig dataclass."""

    def test_defaults(self) -> None:
        config = EvaluatorConfig()
        assert config.provider_name == ""
        assert config.model == ""
        assert config.api_key == ""
        assert config.extra == {}

    def test_custom_values(self) -> None:
        config = EvaluatorConfig(
            provider_name="openai",
            model="gpt-4",
            api_key="sk-...",
            extra={"temperature": 0.5},
        )
        assert config.provider_name == "openai"
        assert config.extra["temperature"] == 0.5
