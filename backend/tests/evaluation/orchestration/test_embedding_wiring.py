"""Tests for embedding-provider wiring into metric execution.

Embedding metrics must receive a real provider instance resolved
through the ProviderRegistry (or fall back to an embedding-capable
chat provider), so they execute against the actual provider boundary
instead of producing fabricated scores.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationMetadata,
)
from app.evaluation.execution.context.context import PipelineContext
from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.pipeline.step import ExecutionStep
from app.evaluation.execution.stages.types import StageType
from app.evaluation.metrics.domain import MetricInput
from app.evaluation.metrics.implementations.relevance_metric import RelevanceMetric
from app.evaluation.orchestration.executor import MetricDispatchStage
from app.providers.models.responses import EmbeddingResponse, Usage
from app.providers.registry.registry import ProviderRegistry


class FakeEmbeddingProvider:
    """Minimal embedding-capable provider fake for registry wiring tests."""

    provider_name = "fake"

    def __init__(self) -> None:
        self.embedded_texts: list[str] = []

    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
        options: Any = None,
    ) -> EmbeddingResponse:
        self.embedded_texts.extend(texts)
        return EmbeddingResponse(
            model=model,
            provider="fake",
            usage=Usage(),
            embedding=(1.0, 0.0, 0.0),
            dimensions=3,
        )


class FakeChatOnlyProvider:
    """Provider without the embedding contract (no embed method)."""

    provider_name = "fake-chat"


def _make_context(metadata: EvaluationMetadata | None = None) -> PipelineContext:
    return PipelineContext(metadata=metadata)


def _make_step(item_index: int = 0) -> ExecutionStep:
    return ExecutionStep.create(
        stage_type=StageType.METRIC_DISPATCH,
        name=f"step_{item_index}",
        item_index=item_index,
        order=item_index,
    )


def _make_plan(total_items: int = 1) -> ExecutionPlan:
    steps = [_make_step(i) for i in range(total_items)]
    return ExecutionPlan.create(
        run_id=None,
        stages=(StageType.METRIC_DISPATCH,),
        steps=steps,
        total_items=total_items,
    )


class TestEmbeddingProviderWiring:
    """_build_metric_metadata must resolve the embedding boundary."""

    def _stage(self, registry: ProviderRegistry | None = None) -> MetricDispatchStage:
        from unittest.mock import MagicMock

        return MetricDispatchStage(metric_engine=MagicMock(), provider_registry=registry)

    def test_explicit_embedding_provider_resolved_from_registry(self) -> None:
        provider = FakeEmbeddingProvider()
        registry = ProviderRegistry()
        registry.register(provider)

        context = _make_context(
            EvaluationMetadata(embedding_provider="fake", embedding_model="emb-1"),
        )
        stage = self._stage(registry)

        metadata = stage._build_metric_metadata(context, _make_step(), 0, {})

        assert metadata["_embedding_provider"] is provider
        assert metadata["_embedding_model"] == "emb-1"

    def test_falls_back_to_embedding_capable_judge_provider(self) -> None:
        chat_provider = FakeEmbeddingProvider()
        registry = ProviderRegistry()
        registry.register(chat_provider)

        context = _make_context(EvaluationMetadata(judge_provider="fake"))
        stage = self._stage(registry)

        metadata = stage._build_metric_metadata(context, _make_step(), 0, {})

        assert metadata["_embedding_provider"] is chat_provider

    def test_chat_only_provider_yields_none_embedding_provider(self) -> None:
        chat_provider = FakeChatOnlyProvider()
        registry = ProviderRegistry()
        registry.register(chat_provider)

        context = _make_context(EvaluationMetadata(judge_provider="fake-chat"))
        stage = self._stage(registry)

        metadata = stage._build_metric_metadata(context, _make_step(), 0, {})

        assert metadata["_embedding_provider"] is None

    def test_unregistered_embedding_provider_degrades_to_none(self) -> None:
        context = _make_context(EvaluationMetadata(embedding_provider="ghost"))
        stage = self._stage(ProviderRegistry())

        metadata = stage._build_metric_metadata(context, _make_step(), 0, {})

        assert metadata["_embedding_provider"] is None

    @pytest.mark.asyncio
    async def test_wired_provider_executes_real_embedding_metric(self) -> None:
        """The injected provider drives a real metric computation."""
        provider = FakeEmbeddingProvider()

        metric = RelevanceMetric()
        result = await metric.evaluate(
            MetricInput(
                prompt="capital of France",
                response="Paris is the capital",
                metadata={"_embedding_provider": provider},
            ),
        )

        assert result.is_success
        assert result.metadata["embedding_model"]
        assert provider.embedded_texts == ["capital of France", "Paris is the capital"]

    @pytest.mark.asyncio
    async def test_missing_embedding_provider_is_explicit_error(self) -> None:
        metric = RelevanceMetric()
        result = await metric.evaluate(
            MetricInput(prompt="p", response="r", metadata={}),
        )

        assert not result.is_success
        assert result.error
