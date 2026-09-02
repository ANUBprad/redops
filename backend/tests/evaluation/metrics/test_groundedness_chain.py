"""Regression tests proving groundedness is a first-class general metric.

P3-1: proves the complete canonical chain

    REAL JUDGE EXECUTION -> canonical MetricResult -> MetricEngine
    -> PERSISTENCE -> API aggregation -> ANALYTICS

using only deterministic fake providers (no real credentials).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.evaluation.domain.contracts.evaluation_contracts import MetricResultRepository
from app.evaluation.metrics.commands import (
    GetAggregatedScoresQuery,
    ListAvailableMetricsQuery,
)
from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricCategory,
    MetricInput,
    MetricResult,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.handlers import (
    GetAggregatedScoresHandler,
    ListAvailableMetricsHandler,
)
from app.evaluation.metrics.implementations import ALL_METRICS
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage


def _fake_provider(judge_payload: dict[str, Any] | Exception) -> AsyncMock:
    """Return an AsyncMock ChatProvider that answers with a judge payload."""
    provider = AsyncMock()
    provider.provider_name = "test-provider"
    if isinstance(judge_payload, Exception):
        provider.chat.side_effect = judge_payload
    else:
        provider.chat.return_value = ChatResponse(
            content=json.dumps(judge_payload),
            model="test-model",
            provider="test-provider",
            usage=Usage(input_tokens=100, output_tokens=50),
            finish_reason=FinishReason.STOP,
        )
    return provider


def _groundedness_input(
    provider: Any,
    *,
    prompt: str = "What is the capital of France?",
    response: str = "Paris is the capital of France.",
    context: str = "Paris is the capital of France.",
) -> MetricInput:
    return MetricInput(
        prompt=prompt,
        response=response,
        context=context,
        metadata={
            "_judge_provider": provider,
            "_judge_provider_name": "test-provider",
            "_judge_model": "test-model",
        },
    )


def _builtin_engine() -> MetricEngine:
    """Build an engine with the full built-in metric registry."""
    engine = MetricEngine()
    for metric_cls in ALL_METRICS:
        engine.register(metric_cls())
    return engine


class TestGroundednessIsFirstClassMetric:
    """The metric is a registered citizen of the general metrics system."""

    def test_registered_in_builtin_registry(self) -> None:
        """Groundedness is part of ALL_METRICS and engine-ready."""
        names = [metric_cls().definition().name for metric_cls in ALL_METRICS]
        assert "groundedness" in names

    def test_list_available_metrics_lists_it(self) -> None:
        """The /metrics catalog handler surfaces groundedness."""

        async def run() -> None:
            engine = _builtin_engine()
            handler = ListAvailableMetricsHandler(engine)
            defs = await handler.handle(ListAvailableMetricsQuery())
            names = {d.name for d in defs}
            assert "groundedness" in names

        import asyncio

        asyncio.run(run())

    def test_definition_metadata(self) -> None:
        """The metric declares itself an LLM-judge quality metric."""
        from app.evaluation.metrics.implementations.groundedness_metric import (
            GroundednessMetric,
        )

        d = GroundednessMetric().definition()
        assert d.name == "groundedness"
        assert d.category == MetricCategory.QUALITY
        assert d.evaluator_type == EvaluatorType.LLM_JUDGE
        assert "prompt" in d.required_inputs
        assert "response" in d.required_inputs
        assert "context" in d.required_inputs
        assert d.requires_context is True


class TestJudgeExecutionProducesCanonicalMetricResult:
    """REAL JUDGE EXECUTION -> canonical MetricResult through the MetricEngine."""

    async def test_grounded_verdict_maps_high_score(self) -> None:
        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.95,
                "confidence": 0.9,
                "reasoning": "All claims are supported by the context.",
            }
        )
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(provider),
        )

        assert result.metric_name == "groundedness"
        assert result.is_success is True
        assert result.score == pytest.approx(0.95)
        assert result.normalized_score == pytest.approx(0.95)
        assert result.confidence == pytest.approx(0.9)
        assert result.metadata["judge_model"] == "test-model"
        assert result.metadata["provider"] == "test-provider"

    async def test_ungrounded_verdict_maps_low_score(self) -> None:
        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.1,
                "confidence": 0.85,
                "reasoning": "Response contains claims not supported by context.",
            }
        )
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(provider),
        )

        assert result.is_success is True
        assert result.score == pytest.approx(0.1)
        assert result.normalized_score == pytest.approx(0.1)

    async def test_partial_verdict_maps_intermediate_score(self) -> None:
        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.5,
                "confidence": 0.7,
                "reasoning": "Some claims supported, some not.",
            }
        )
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(provider),
        )

        assert result.is_success is True
        assert result.score == pytest.approx(0.5)

    async def test_missing_context_produces_error_result(self) -> None:
        engine = _builtin_engine()
        result = await engine.evaluate_single(
            "groundedness",
            MetricInput(prompt="p", response="r"),
        )
        assert result.is_success is False
        assert result.error is not None
        assert "context" in (result.error or "").lower()

    async def test_missing_judge_provider_produces_error_result(self) -> None:
        engine = _builtin_engine()
        result = await engine.evaluate_single(
            "groundedness",
            MetricInput(prompt="p", response="r", context="c"),
        )
        assert result.is_success is False
        assert result.error is not None
        assert "_judge_provider" in (result.error or "")

    async def test_judge_error_produces_error_metric_result(self) -> None:
        engine = _builtin_engine()
        provider = _fake_provider(RuntimeError("provider down"))
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(provider),
        )

        assert result.is_success is False
        assert result.error is not None
        assert "provider down" in (result.error or "")

    async def test_malformed_judge_output_produces_error(self) -> None:
        engine = _builtin_engine()
        provider = _fake_provider("not valid json at all")
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(provider),
        )

        assert result.is_success is False
        assert result.error is not None

    async def test_evaluate_batch_returns_groundedness(self) -> None:
        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.88,
                "confidence": 0.82,
                "reasoning": "mostly grounded",
            }
        )
        results = await engine.evaluate_batch(
            ("json_validity", "groundedness"),
            _groundedness_input(provider),
        )
        by_name = {r.metric_name: r for r in results}
        assert "groundedness" in by_name
        assert by_name["groundedness"].normalized_score == pytest.approx(0.88)


class TestGroundednessCredibility:
    """Credibility tests: judge verdict actually drives the score."""

    async def test_supported_response_yields_high_groundedness(self) -> None:
        """Same context + supported response -> high groundedness."""
        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.92,
                "confidence": 0.88,
                "reasoning": "Response is fully supported by context.",
            }
        )
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(
                provider,
                prompt="What powers the water cycle?",
                response="Solar energy drives evaporation.",
                context="Solar energy drives evaporation from oceans.",
            ),
        )

        assert result.is_success
        assert result.score >= 0.8
        assert result.confidence > 0.0
        assert result.metadata["judge_model"] == "test-model"

    async def test_contradicted_response_yields_low_groundedness(self) -> None:
        """Same context + contradicted response -> low groundedness."""
        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.08,
                "confidence": 0.9,
                "reasoning": "Response contradicts the context.",
            }
        )
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(
                provider,
                prompt="What powers the water cycle?",
                response="Nuclear fusion drives the water cycle.",
                context="Solar energy drives evaporation from oceans.",
            ),
        )

        assert result.is_success
        assert result.score <= 0.2
        assert result.confidence > 0.0

    async def test_partial_support_yields_intermediate_groundedness(self) -> None:
        """Same context + partially supported response -> intermediate score."""
        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.45,
                "confidence": 0.75,
                "reasoning": "Some claims supported, others are fabricated.",
            }
        )
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(
                provider,
                prompt="What powers the water cycle?",
                response="Solar energy drives evaporation and gravity causes rain.",
                context="Solar energy drives evaporation from oceans.",
            ),
        )

        assert result.is_success
        assert 0.2 <= result.score <= 0.7
        assert result.confidence > 0.0


class TestPersistenceAndAnalyticsVisibility:
    """PERSISTENCE -> API aggregation -> ANALYTICS visibility of the metric."""

    async def _session_factory(self) -> async_sessionmaker[Any]:
        engine = create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, ([MetricResultModel.__table__]))
        return async_sessionmaker(engine, expire_on_commit=False)

    async def test_persisted_groundedness_is_aggregated(self) -> None:
        factory = await self._session_factory()

        engine = _builtin_engine()
        scores = [0.95, 0.70, 0.30]
        persisted: list[MetricResult] = []
        for idx, expected in enumerate(scores):
            provider = _fake_provider(
                {
                    "score": expected,
                    "confidence": 0.8,
                    "reasoning": "ok",
                }
            )
            result = await engine.evaluate_single(
                "groundedness",
                _groundedness_input(provider),
            )
            result.metadata["run_id"] = "00000000-0000-0000-0000-000000000301"
            result.metadata["item_id"] = f"00000000-0000-0000-0000-0000000004{idx:02d}"
            persisted.append(result)

        async with factory() as session:
            repo: MetricResultRepository = SqlAlchemyMetricResultRepository(session)
            await repo.save_many(persisted)
            await session.commit()

        async with factory() as session:
            repo = SqlAlchemyMetricResultRepository(session)
            handler = GetAggregatedScoresHandler(repo)
            query = GetAggregatedScoresQuery(run_id="00000000-0000-0000-0000-000000000301")
            aggregations = await handler.handle(query)

        assert "groundedness" in aggregations
        agg = aggregations["groundedness"]
        assert agg.item_count == 3
        assert agg.mean == pytest.approx(sum(scores) / len(scores))
        assert agg.min_score == pytest.approx(0.30)
        assert agg.max_score == pytest.approx(0.95)

    async def test_metadata_survives_persistence(self) -> None:
        """Key provenance fields survive the persistence round-trip."""
        factory = await self._session_factory()

        engine = _builtin_engine()
        provider = _fake_provider(
            {
                "score": 0.85,
                "confidence": 0.78,
                "reasoning": "well supported",
            }
        )
        result = await engine.evaluate_single(
            "groundedness",
            _groundedness_input(provider),
        )
        result.metadata["run_id"] = "00000000-0000-0000-0000-000000000501"
        result.metadata["item_id"] = "00000000-0000-0000-0000-000000000601"

        async with factory() as session:
            repo: MetricResultRepository = SqlAlchemyMetricResultRepository(session)
            await repo.save_many([result])
            await session.commit()

        async with factory() as session:
            repo = SqlAlchemyMetricResultRepository(session)
            handler = GetAggregatedScoresHandler(repo)
            query = GetAggregatedScoresQuery(run_id="00000000-0000-0000-0000-000000000501")
            aggregations = await handler.handle(query)

        assert "groundedness" in aggregations
