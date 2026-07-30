"""Tests for the metrics engine domain and implementations."""

from __future__ import annotations

import pytest

from app.evaluation.metrics.domain import (
    MetricAggregation,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations import ALL_METRICS


class TestMetricResult:
    """Tests for MetricResult value object."""

    def test_successful_result(self) -> None:
        """Successful result has no error."""
        result = MetricResult(
            metric_name="test",
            score=0.8,
            normalized_score=0.8,
        )
        assert result.is_success is True
        assert result.is_valid_score is True

    def test_error_result(self) -> None:
        """Error result has error field set."""
        result = MetricResult(
            metric_name="test",
            score=0.0,
            normalized_score=0.0,
            error="something went wrong",
        )
        assert result.is_success is False

    def test_invalid_normalized_score(self) -> None:
        """Score outside [0.0, 1.0] is detected."""
        result = MetricResult(
            metric_name="test",
            score=1.5,
            normalized_score=1.5,
        )
        assert result.is_valid_score is False

    def test_zero_scores_valid(self) -> None:
        """Zero scores are valid."""
        result = MetricResult(
            metric_name="test",
            score=0.0,
            normalized_score=0.0,
        )
        assert result.is_valid_score is True


class TestMetricAggregation:
    """Tests for MetricAggregation."""

    def test_empty_results(self) -> None:
        """Empty results produce zero aggregation."""
        agg = MetricAggregation.from_results("test", ())
        assert agg.item_count == 0
        assert agg.mean == 0.0

    def test_single_result(self) -> None:
        """Single result produces matching aggregation."""
        result = MetricResult(
            metric_name="test",
            score=0.8,
            normalized_score=0.8,
        )
        agg = MetricAggregation.from_results("test", (result,))
        assert agg.mean == 0.8
        assert agg.min_score == 0.8
        assert agg.max_score == 0.8
        assert agg.item_count == 1

    def test_multiple_results(self) -> None:
        """Multiple results compute correct statistics."""
        results = tuple(
            MetricResult(
                metric_name="test",
                score=float(i) / 10,
                normalized_score=float(i) / 10,
            )
            for i in range(10)
        )
        agg = MetricAggregation.from_results("test", results)
        assert agg.item_count == 10
        assert agg.min_score == 0.0
        assert agg.max_score == 0.9
        assert 0.4 <= agg.mean <= 0.5

    def test_mixed_success_error(self) -> None:
        """Mixed success/error results count correctly."""
        results = (
            MetricResult(metric_name="test", score=0.8, normalized_score=0.8),
            MetricResult(
                metric_name="test",
                score=0.0,
                normalized_score=0.0,
                error="failed",
            ),
        )
        agg = MetricAggregation.from_results("test", results)
        assert agg.item_count == 2
        assert agg.success_count == 1
        assert agg.error_count == 1
        assert agg.success_rate == 0.5

    def test_success_rate_zero_items(self) -> None:
        """Success rate is 0 for empty results."""
        agg = MetricAggregation.from_results("test", ())
        assert agg.success_rate == 0.0


class TestMetricDefinition:
    """Tests for MetricDefinition value object."""

    def test_quality_metric(self) -> None:
        """Quality metric detection works."""
        defn = MetricDefinition(
            name="test",
            display_name="Test",
            description="Test metric",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
        )
        assert defn.is_quality_metric is True
        assert defn.is_performance_metric is False

    def test_performance_metric(self) -> None:
        """Performance metric detection works."""
        defn = MetricDefinition(
            name="test",
            display_name="Test",
            description="Test metric",
            category=MetricCategory.PERFORMANCE,
            scale=MetricScale.CONTINUOUS,
        )
        assert defn.is_performance_metric is True


class TestMetricEngine:
    """Tests for MetricEngine orchestrator."""

    @pytest.fixture
    def engine(self) -> MetricEngine:
        """Create a fresh MetricEngine."""
        return MetricEngine()

    def test_register_metric(self) -> None:
        """Metric can be registered."""
        engine = MetricEngine()
        metric = ALL_METRICS[0]()
        engine.register(metric)
        assert engine.metric_count == 1

    def test_register_duplicate_raises(self) -> None:
        """Duplicate metric registration raises ValueError."""
        engine = MetricEngine()
        metric = ALL_METRICS[0]()
        engine.register(metric)
        with pytest.raises(ValueError, match="already registered"):
            engine.register(metric)

    def test_unregister_metric(self) -> None:
        """Metric can be unregistered."""
        engine = MetricEngine()
        metric = ALL_METRICS[0]()
        engine.register(metric)
        engine.unregister(metric.definition().name)
        assert engine.metric_count == 0

    def test_get_metric(self) -> None:
        """Metric can be retrieved by name."""
        engine = MetricEngine()
        metric = ALL_METRICS[0]()
        engine.register(metric)
        retrieved = engine.get(metric.definition().name)
        assert retrieved is metric

    def test_get_nonexistent_returns_none(self) -> None:
        """Non-existent metric returns None."""
        engine = MetricEngine()
        assert engine.get("nonexistent") is None

    def test_has_metric(self) -> None:
        """has_metric checks registration."""
        engine = MetricEngine()
        metric = ALL_METRICS[0]()
        engine.register(metric)
        assert engine.has_metric(metric.definition().name)
        assert not engine.has_metric("nonexistent")

    def test_list_definitions(self) -> None:
        """All definitions can be listed."""
        engine = MetricEngine()
        for cls in ALL_METRICS:
            engine.register(cls())
        defs = engine.list_definitions()
        assert len(defs) == len(ALL_METRICS)

    def test_list_by_category(self) -> None:
        """Definitions can be filtered by category."""
        engine = MetricEngine()
        for cls in ALL_METRICS:
            engine.register(cls())
        quality = engine.list_by_category(MetricCategory.QUALITY)
        assert all(d.category == MetricCategory.QUALITY for d in quality)

    def test_resolve_metrics(self) -> None:
        """resolve_metrics filters to registered names."""
        engine = MetricEngine()
        for cls in ALL_METRICS:
            engine.register(cls())
        names = tuple(d.name for d in engine.list_definitions())
        resolved = engine.resolve_metrics(names + ("nonexistent",))
        assert len(resolved) == len(names)

    @pytest.mark.asyncio
    async def test_evaluate_single(self) -> None:
        """Single metric evaluation works."""
        engine = MetricEngine()
        metric = ALL_METRICS[0]()
        engine.register(metric)
        result = await engine.evaluate_single(
            metric.definition().name,
            MetricInput(prompt="hello world", response="hello world"),
        )
        assert result.metric_name == metric.definition().name

    @pytest.mark.asyncio
    async def test_evaluate_single_unknown_raises(self) -> None:
        """Unknown metric raises KeyError."""
        engine = MetricEngine()
        with pytest.raises(KeyError):
            await engine.evaluate_single("unknown", MetricInput())

    @pytest.mark.asyncio
    async def test_evaluate_batch(self) -> None:
        """Batch evaluation works."""
        engine = MetricEngine()
        for cls in ALL_METRICS:
            engine.register(cls())
        names = tuple(d.name for d in engine.list_definitions())
        results = await engine.evaluate_batch(
            names,
            MetricInput(prompt="test", response="test response"),
        )
        assert len(results) == len(names)
