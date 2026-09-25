"""Tests for composite metric implementations.

Covers AverageCompositeMetric and WeightedCompositeMetric, including
aggregation logic, error handling, and MetricEngine integration.
"""

from __future__ import annotations

import pytest

from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations.composite import (
    AverageCompositeMetric,
    CompositeComponent,
    WeightedCompositeMetric,
)


class _ConstMetric(Metric):
    """A metric that returns a fixed score."""

    def __init__(self, name: str, score: float) -> None:
        self._name = name
        self._score = score

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name=self._name,
            display_name=self._name,
            description="const",
            category=MetricCategory.QUALITY,
            scale=MetricScale.BINARY,
            evaluator_type=EvaluatorType.HEURISTIC,
            required_inputs=("prompt",),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        return MetricResult(
            metric_name=self._name,
            score=self._score,
            normalized_score=self._score,
            version="1.0.0",
        )


class TestCompositeComponent:
    """Tests for the CompositeComponent dataclass."""

    def test_defaults(self) -> None:
        comp = CompositeComponent(metric_name="test")
        assert comp.metric_name == "test"
        assert comp.weight == 1.0

    def test_custom_weight(self) -> None:
        comp = CompositeComponent(metric_name="test", weight=2.5)
        assert comp.weight == 2.5

    def test_frozen(self) -> None:
        comp = CompositeComponent(metric_name="test")
        with pytest.raises(AttributeError):
            comp.metric_name = "changed"  # type: ignore[misc]


class TestAverageCompositeMetric:
    """Tests for AverageCompositeMetric."""

    def test_definition(self) -> None:
        metric = AverageCompositeMetric(
            name="avg_test",
            display_name="Avg Test",
            description="Test average",
            components=[
                CompositeComponent(metric_name="a"),
                CompositeComponent(metric_name="b"),
            ],
        )
        defn = metric.definition()
        assert defn.name == "avg_test"
        assert defn.category.value == "composite"
        assert defn.evaluator_type.value == "custom"

    def test_components_property(self) -> None:
        comps = [
            CompositeComponent(metric_name="a"),
            CompositeComponent(metric_name="b", weight=2.0),
        ]
        metric = AverageCompositeMetric(
            name="avg",
            display_name="Avg",
            description="",
            components=comps,
        )
        assert len(metric.components) == 2
        assert metric.components[0].metric_name == "a"
        assert metric.components[1].weight == 2.0

    @pytest.mark.asyncio
    async def test_aggregate_scores_equal(self) -> None:
        metric = AverageCompositeMetric(
            name="avg",
            display_name="Avg",
            description="",
            components=[
                CompositeComponent(metric_name="a"),
                CompositeComponent(metric_name="b"),
            ],
        )
        results = {
            "a": MetricResult(metric_name="a", score=0.8, normalized_score=0.8),
            "b": MetricResult(metric_name="b", score=0.6, normalized_score=0.6),
        }
        assert metric.aggregate_scores(results) == pytest.approx(0.7)

    @pytest.mark.asyncio
    async def test_aggregate_scores_all_failed(self) -> None:
        metric = AverageCompositeMetric(
            name="avg",
            display_name="Avg",
            description="",
            components=[CompositeComponent(metric_name="a")],
        )
        results = {
            "a": MetricResult(
                metric_name="a",
                score=0.0,
                normalized_score=0.0,
                error="fail",
            ),
        }
        assert metric.aggregate_scores(results) == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_raises_not_implemented(self) -> None:
        metric = AverageCompositeMetric(
            name="avg",
            display_name="Avg",
            description="",
            components=[CompositeComponent(metric_name="a")],
        )
        with pytest.raises(NotImplementedError, match="requires the MetricEngine"):
            await metric.evaluate(MetricInput(prompt="test"))

    @pytest.mark.asyncio
    async def test_evaluate_with_engine(self) -> None:
        engine = MetricEngine()
        m1 = _ConstMetric("metric_a", 0.8)
        m2 = _ConstMetric("metric_b", 0.6)
        engine.register(m1)
        engine.register(m2)

        composite = AverageCompositeMetric(
            name="my_avg",
            display_name="My Avg",
            description="Average of two metrics",
            components=[
                CompositeComponent(metric_name="metric_a"),
                CompositeComponent(metric_name="metric_b"),
            ],
        )

        input_data = MetricInput(prompt="test", response="response")
        result = await composite.evaluate_with_engine(input_data, engine)
        assert result.metric_name == "my_avg"
        assert result.score == pytest.approx(0.7)
        assert result.is_success

    @pytest.mark.asyncio
    async def test_evaluate_with_engine_partial_failure(self) -> None:
        engine = MetricEngine()
        m1 = _ConstMetric("good", 1.0)
        engine.register(m1)

        composite = AverageCompositeMetric(
            name="partial_avg",
            display_name="Partial",
            description="",
            components=[
                CompositeComponent(metric_name="good"),
                CompositeComponent(metric_name="nonexistent"),
            ],
        )

        result = await composite.evaluate_with_engine(
            MetricInput(prompt="test"),
            engine,
        )
        # Should succeed with only the good metric's score
        assert result.is_success
        assert result.score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_evaluate_with_engine_all_fail(self) -> None:
        engine = MetricEngine()
        composite = AverageCompositeMetric(
            name="fail_avg",
            display_name="Fail",
            description="",
            components=[CompositeComponent(metric_name="missing")],
        )
        result = await composite.evaluate_with_engine(
            MetricInput(prompt="test"),
            engine,
        )
        assert not result.is_success
        assert "All component metrics failed" in result.error  # type: ignore[union-attr]


class TestWeightedCompositeMetric:
    """Tests for WeightedCompositeMetric."""

    def test_definition(self) -> None:
        metric = WeightedCompositeMetric(
            name="weighted_test",
            display_name="Weighted Test",
            description="Test weighted",
            components=[
                CompositeComponent(metric_name="a", weight=3.0),
                CompositeComponent(metric_name="b", weight=1.0),
            ],
        )
        defn = metric.definition()
        assert defn.name == "weighted_test"

    @pytest.mark.asyncio
    async def test_aggregate_scores_weighted(self) -> None:
        metric = WeightedCompositeMetric(
            name="wavg",
            display_name="WAvg",
            description="",
            components=[
                CompositeComponent(metric_name="a", weight=3.0),
                CompositeComponent(metric_name="b", weight=1.0),
            ],
        )
        results = {
            "a": MetricResult(metric_name="a", score=1.0, normalized_score=1.0),
            "b": MetricResult(metric_name="b", score=0.0, normalized_score=0.0),
        }
        # (1.0 * 3 + 0.0 * 1) / (3 + 1) = 0.75
        assert metric.aggregate_scores(results) == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_aggregate_scores_partial_failure(self) -> None:
        metric = WeightedCompositeMetric(
            name="wavg",
            display_name="WAvg",
            description="",
            components=[
                CompositeComponent(metric_name="a", weight=2.0),
                CompositeComponent(metric_name="b", weight=1.0),
            ],
        )
        results = {
            "a": MetricResult(metric_name="a", score=0.9, normalized_score=0.9),
            "b": MetricResult(
                metric_name="b",
                score=0.0,
                normalized_score=0.0,
                error="fail",
            ),
        }
        # Only a succeeds: (0.9 * 2) / 2 = 0.9
        assert metric.aggregate_scores(results) == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_aggregate_scores_all_zero_weight(self) -> None:
        metric = WeightedCompositeMetric(
            name="wavg",
            display_name="WAvg",
            description="",
            components=[
                CompositeComponent(metric_name="a", weight=0.0),
            ],
        )
        results = {
            "a": MetricResult(metric_name="a", score=1.0, normalized_score=1.0),
        }
        assert metric.aggregate_scores(results) == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_with_engine(self) -> None:
        engine = MetricEngine()
        engine.register(_ConstMetric("fast", 0.9))
        engine.register(_ConstMetric("slow", 0.3))

        composite = WeightedCompositeMetric(
            name="perf_score",
            display_name="Performance Score",
            description="Weighted performance",
            components=[
                CompositeComponent(metric_name="fast", weight=2.0),
                CompositeComponent(metric_name="slow", weight=1.0),
            ],
        )

        result = await composite.evaluate_with_engine(
            MetricInput(prompt="test"),
            engine,
        )
        assert result.metric_name == "perf_score"
        # (0.9 * 2 + 0.3 * 1) / 3 = 2.1 / 3 = 0.7
        assert result.score == pytest.approx(0.7)
        assert result.is_success
