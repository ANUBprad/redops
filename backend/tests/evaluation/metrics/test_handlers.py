"""Tests for metrics engine handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.domain.contracts.evaluation_contracts import MetricResultRepository
from app.evaluation.metrics.commands import (
    GetAggregatedScoresQuery,
    ListAvailableMetricsQuery,
    ScoreItemCommand,
)
from app.evaluation.metrics.domain import (
    Metric,
    MetricInput,
    MetricResult,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.handlers import (
    GetAggregatedScoresHandler,
    ListAvailableMetricsHandler,
    ScoreItemHandler,
)
from app.evaluation.metrics.implementations import ALL_METRICS


@pytest.fixture
def engine() -> MetricEngine:
    """Create a MetricEngine with all built-in metrics."""
    eng = MetricEngine()
    for cls in ALL_METRICS:
        eng.register(cls())
    return eng


@pytest.fixture
def mock_repo() -> MetricResultRepository:
    """Create a mock MetricResultRepository."""
    repo = MagicMock(spec=MetricResultRepository)
    repo.save_many = AsyncMock()
    repo.find_by_run_id = AsyncMock(return_value=[])
    repo.find_by_item_id = AsyncMock(return_value=[])
    return repo


class TestScoreItemHandler:
    """Tests for ScoreItemHandler."""

    @pytest.mark.asyncio
    async def test_score_with_all_metrics(
        self,
        engine: MetricEngine,
        mock_repo: MetricResultRepository,
    ) -> None:
        """Score with all metrics returns results for each."""
        handler = ScoreItemHandler(engine, mock_repo)
        command = ScoreItemCommand(
            run_id="00000000-0000-0000-0000-000000000001",
            item_id="00000000-0000-0000-0000-000000000002",
            prompt="test prompt",
            response="test response",
        )
        results = await handler.handle(command)
        assert len(results) == len(ALL_METRICS)
        mock_repo.save_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_score_with_specific_metrics(
        self,
        engine: MetricEngine,
        mock_repo: MetricResultRepository,
    ) -> None:
        """Score with specific metrics returns only those results."""
        handler = ScoreItemHandler(engine, mock_repo)
        command = ScoreItemCommand(
            run_id="00000000-0000-0000-0000-000000000001",
            item_id="00000000-0000-0000-0000-000000000002",
            metric_names=("answer_relevance", "correctness"),
        )
        results = await handler.handle(command)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_score_with_no_metrics(
        self,
        engine: MetricEngine,
        mock_repo: MetricResultRepository,
    ) -> None:
        """Score with empty metric names uses all metrics."""
        handler = ScoreItemHandler(engine, mock_repo)
        command = ScoreItemCommand(
            run_id="00000000-0000-0000-0000-000000000001",
            item_id="00000000-0000-0000-0000-000000000002",
            metric_names=(),
        )
        results = await handler.handle(command)
        assert len(results) == len(ALL_METRICS)

    @pytest.mark.asyncio
    async def test_score_saves_successful_results(
        self,
        engine: MetricEngine,
        mock_repo: MetricResultRepository,
    ) -> None:
        """Only successful results are saved to repository."""
        handler = ScoreItemHandler(engine, mock_repo)
        command = ScoreItemCommand(
            run_id="00000000-0000-0000-0000-000000000001",
            item_id="00000000-0000-0000-0000-000000000002",
            metric_names=("relevance",),
        )
        results = await handler.handle(command)
        if any(r.is_success for r in results):
            mock_repo.save_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_enriches_metadata_with_run_and_item_ids(
        self,
        engine: MetricEngine,
        mock_repo: MetricResultRepository,
    ) -> None:
        """Saved results contain run_id and item_id in metadata."""
        handler = ScoreItemHandler(engine, mock_repo)
        command = ScoreItemCommand(
            run_id="00000000-0000-0000-0000-000000000001",
            item_id="00000000-0000-0000-0000-000000000002",
            prompt="test prompt",
            response="test response",
        )
        await handler.handle(command)

        call_args = mock_repo.save_many.call_args
        assert call_args is not None
        saved_results = call_args[0][0]
        for r in saved_results:
            assert r.metadata.get("run_id") == "00000000-0000-0000-0000-000000000001"
            assert r.metadata.get("item_id") == "00000000-0000-0000-0000-000000000002"

    @pytest.mark.asyncio
    async def test_enrichment_preserves_confidence_cost_and_version(
        self,
        engine: MetricEngine,
        mock_repo: MetricResultRepository,
    ) -> None:
        """Reconstructed results keep confidence, cost_usd, and version.

        The handler reconstructs each result to stamp run/item identity
        before persisting. It must not silently reset confidence,
        cost_usd, or version to their dataclass defaults.
        """
        from app.evaluation.metrics.domain import (
            MetricCategory,
            MetricDefinition,
            MetricScale,
        )

        class StubMetric(Metric):
            """Purely deterministic metric for asserting preservation."""

            def definition(self) -> MetricDefinition:
                return MetricDefinition(
                    name="stub",
                    display_name="Stub",
                    description="test",
                    category=MetricCategory.QUALITY,
                    scale=MetricScale.CONTINUOUS,
                    version="3.2.1",
                )

            async def evaluate(self, input_data: MetricInput) -> MetricResult:
                return MetricResult(
                    metric_name="stub",
                    score=0.5,
                    normalized_score=0.5,
                    confidence=0.9,
                    cost_usd=0.0123,
                    version="3.2.1",
                )

        engine.register(StubMetric())
        handler = ScoreItemHandler(engine, mock_repo)
        command = ScoreItemCommand(
            run_id="00000000-0000-0000-0000-000000000001",
            item_id="00000000-0000-0000-0000-000000000002",
            metric_names=("stub",),
        )
        await handler.handle(command)

        call_args = mock_repo.save_many.call_args
        assert call_args is not None
        saved_results = call_args[0][0]
        assert len(saved_results) == 1
        assert saved_results[0].confidence == pytest.approx(0.9)
        assert saved_results[0].cost_usd == pytest.approx(0.0123)
        assert saved_results[0].version == "3.2.1"


class TestGetAggregatedScoresHandler:
    """Tests for GetAggregatedScoresHandler."""

    @pytest.mark.asyncio
    async def test_empty_results(self, mock_repo: MetricResultRepository) -> None:
        """Empty results produce empty aggregations."""
        mock_repo.find_by_run_id = AsyncMock(return_value=[])
        handler = GetAggregatedScoresHandler(mock_repo)
        query = GetAggregatedScoresQuery(run_id="00000000-0000-0000-0000-000000000001")
        result = await handler.handle(query)
        assert result == {}

    @pytest.mark.asyncio
    async def test_with_results(self, mock_repo: MetricResultRepository) -> None:
        """Results are aggregated by metric name."""
        mock_repo.find_by_run_id = AsyncMock(
            return_value=[
                MetricResult(metric_name="relevance", score=0.8, normalized_score=0.8),
                MetricResult(metric_name="relevance", score=0.6, normalized_score=0.6),
                MetricResult(metric_name="correctness", score=0.9, normalized_score=0.9),
            ],
        )
        handler = GetAggregatedScoresHandler(mock_repo)
        query = GetAggregatedScoresQuery(run_id="00000000-0000-0000-0000-000000000001")
        result = await handler.handle(query)
        assert "relevance" in result
        assert "correctness" in result
        assert result["relevance"].item_count == 2
        assert result["correctness"].item_count == 1

    @pytest.mark.asyncio
    async def test_filter_by_metric_name(
        self,
        mock_repo: MetricResultRepository,
    ) -> None:
        """Filtering by metric name returns only matching results."""
        mock_repo.find_by_run_id = AsyncMock(
            return_value=[
                MetricResult(metric_name="relevance", score=0.8, normalized_score=0.8),
            ],
        )
        handler = GetAggregatedScoresHandler(mock_repo)
        query = GetAggregatedScoresQuery(
            run_id="00000000-0000-0000-0000-000000000001",
            metric_name="relevance",
        )
        result = await handler.handle(query)
        assert "relevance" in result
        mock_repo.find_by_run_id.assert_called_once_with(
            mock_repo.find_by_run_id.call_args[0][0],
            metric_name="relevance",
        )


class TestListAvailableMetricsHandler:
    """Tests for ListAvailableMetricsHandler."""

    @pytest.mark.asyncio
    async def test_list_all(self, engine: MetricEngine) -> None:
        """List all metrics returns all definitions."""
        handler = ListAvailableMetricsHandler(engine)
        query = ListAvailableMetricsQuery()
        result = await handler.handle(query)
        assert len(result) == len(ALL_METRICS)

    @pytest.mark.asyncio
    async def test_list_by_category(self, engine: MetricEngine) -> None:
        """Filtering by category works."""
        handler = ListAvailableMetricsHandler(engine)
        query = ListAvailableMetricsQuery(category="quality")
        result = await handler.handle(query)
        assert all(d.category.value == "quality" for d in result)

    @pytest.mark.asyncio
    async def test_invalid_category_raises(self, engine: MetricEngine) -> None:
        """Invalid category raises ValidationError."""
        from app.kernel.exceptions.errors import ValidationError

        handler = ListAvailableMetricsHandler(engine)
        query = ListAvailableMetricsQuery(category="invalid")
        with pytest.raises(ValidationError):
            await handler.handle(query)
