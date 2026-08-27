"""Tests for the MetricRegistry.

Covers registration, validation, discovery, to_db_records, and filtering.
"""

from __future__ import annotations

from unittest.mock import patch

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
from app.evaluation.metrics.registry import MetricRegistry


class _DummyMetric(Metric):
    """Minimal metric for testing."""

    def __init__(
        self,
        name: str = "test_metric",
        display_name: str = "Test Metric",
        evaluator_type: EvaluatorType = EvaluatorType.HEURISTIC,
        required_inputs: tuple[str, ...] = ("prompt",),
        version: str = "1.0.0",
    ) -> None:
        self._name = name
        self._display_name = display_name
        self._evaluator_type = evaluator_type
        self._required_inputs = required_inputs
        self._version = version

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name=self._name,
            display_name=self._display_name,
            description="A test metric",
            category=MetricCategory.QUALITY,
            scale=MetricScale.BINARY,
            version=self._version,
            evaluator_type=self._evaluator_type,
            required_inputs=self._required_inputs,
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        return MetricResult(
            metric_name=self._name,
            score=1.0,
            normalized_score=1.0,
            version=self._version,
        )


class TestMetricRegistry:
    """Tests for MetricRegistry registration and lookup."""

    def test_empty_registry(self) -> None:
        registry = MetricRegistry()
        assert registry.metric_count == 0
        assert registry.get_all() == []

    def test_register_single(self) -> None:
        registry = MetricRegistry()
        metric = _DummyMetric()
        registry.register(metric)
        assert registry.metric_count == 1
        assert registry.get("test_metric") is metric
        assert registry.has_metric("test_metric")

    def test_register_with_plugin_module(self) -> None:
        registry = MetricRegistry()
        metric = _DummyMetric()
        registry.register(metric, plugin_module="my_plugin.metrics")
        assert registry.metric_count == 1
        # Plugin metrics should appear in list_plugin_metrics
        plugins = registry.list_plugin_metrics()
        assert len(plugins) == 1
        assert plugins[0].name == "test_metric"

    def test_register_builtin(self) -> None:
        registry = MetricRegistry()
        m1 = _DummyMetric(name="metric_a")
        m2 = _DummyMetric(name="metric_b")
        registry.register_builtin([m1, m2])
        assert registry.metric_count == 2
        assert registry.has_metric("metric_a")
        assert registry.has_metric("metric_b")

    def test_register_duplicate_raises(self) -> None:
        registry = MetricRegistry()
        m1 = _DummyMetric(name="dup")
        m2 = _DummyMetric(name="dup")
        registry.register(m1)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(m2)

    def test_register_invalid_metric_raises(self) -> None:
        registry = MetricRegistry()
        # Metric with empty required_inputs
        bad_metric = _DummyMetric(required_inputs=())
        with pytest.raises(ValueError, match="at least one required_input"):
            registry.register(bad_metric)

    def test_register_invalid_evaluator_type_raises(self) -> None:
        registry = MetricRegistry()
        # Create a metric with an invalid evaluator type
        class _BadMetric(Metric):
            def definition(self) -> MetricDefinition:
                return MetricDefinition(
                    name="bad",
                    display_name="Bad",
                    description="",
                    category=MetricCategory.QUALITY,
                    scale=MetricScale.BINARY,
                    evaluator_type="not_a_valid_type",  # type: ignore[arg-type]
                    required_inputs=("prompt",),
                )

            async def evaluate(self, input_data: MetricInput) -> MetricResult:
                return MetricResult(metric_name="bad", score=0.0, normalized_score=0.0)

        with pytest.raises(ValueError, match="invalid evaluator_type"):
            registry.register(_BadMetric())

    def test_get_nonexistent_returns_none(self) -> None:
        registry = MetricRegistry()
        assert registry.get("nonexistent") is None
        assert registry.get_definition("nonexistent") is None

    def test_get_definition(self) -> None:
        registry = MetricRegistry()
        metric = _DummyMetric(name="def_test")
        registry.register(metric)
        defn = registry.get_definition("def_test")
        assert defn is not None
        assert defn.name == "def_test"

    def test_list_definitions(self) -> None:
        registry = MetricRegistry()
        registry.register(_DummyMetric(name="a"))
        registry.register(_DummyMetric(name="b"))
        defs = registry.list_definitions()
        assert len(defs) == 2
        names = {d.name for d in defs}
        assert names == {"a", "b"}


class TestMetricRegistryFiltering:
    """Tests for category and evaluator type filtering."""

    def test_list_by_category(self) -> None:
        registry = MetricRegistry()
        registry.register(_DummyMetric(name="correctness_m"))
        registry.register(
            _DummyMetric(
                name="relevance_m",
                display_name="Relevance",
            )
        )
        # All default to QUALITY, so list_by_category should find both
        results = registry.list_by_category(MetricCategory.QUALITY)
        assert len(results) == 2

    def test_list_by_evaluator_type(self) -> None:
        registry = MetricRegistry()
        registry.register(_DummyMetric(name="heuristic_m"))
        registry.register(
            _DummyMetric(
                name="custom_m",
                evaluator_type=EvaluatorType.CUSTOM,
            )
        )
        heuristic = registry.list_by_evaluator_type(EvaluatorType.HEURISTIC)
        assert len(heuristic) == 1
        assert heuristic[0].name == "heuristic_m"

        custom = registry.list_by_evaluator_type(EvaluatorType.CUSTOM)
        assert len(custom) == 1
        assert custom[0].name == "custom_m"


class TestMetricRegistryDiscovery:
    """Tests for external plugin discovery."""

    def test_discover_external_no_plugins(self) -> None:
        registry = MetricRegistry()
        with patch(
            "app.evaluation.metrics.registry.importlib.metadata.entry_points",
            return_value=[],
        ):
            discovered = registry.discover_external()
        assert discovered == []

    def test_discover_external_with_plugin(self) -> None:
        from types import SimpleNamespace

        registry = MetricRegistry()

        class _PluginMetric(Metric):
            def definition(self) -> MetricDefinition:
                return MetricDefinition(
                    name="plugin_metric",
                    display_name="Plugin Metric",
                    description="",
                    category=MetricCategory.QUALITY,
                    scale=MetricScale.BINARY,
                    evaluator_type=EvaluatorType.CUSTOM,
                    required_inputs=("prompt",),
                )

            async def evaluate(self, input_data: MetricInput) -> MetricResult:
                return MetricResult(metric_name="plugin_metric", score=1.0, normalized_score=1.0)

        fake_ep = SimpleNamespace(
            name="my_plugin",
            value="my_plugin.metrics:MyMetric",
            load=lambda: _PluginMetric,
        )
        with patch(
            "app.evaluation.metrics.registry.importlib.metadata.entry_points",
            return_value=[fake_ep],
        ):
            discovered = registry.discover_external()
        assert discovered == ["plugin_metric"]
        assert registry.has_metric("plugin_metric")

    def test_discover_external_non_metric_ignored(self) -> None:
        from types import SimpleNamespace

        registry = MetricRegistry()
        fake_ep = SimpleNamespace(
            name="bad_plugin",
            value="bad_plugin:NotAMetric",
            load=lambda: str,  # Not a Metric subclass
        )
        with patch(
            "app.evaluation.metrics.registry.importlib.metadata.entry_points",
            return_value=[fake_ep],
        ):
            discovered = registry.discover_external()
        assert discovered == []
        assert registry.metric_count == 0

    def test_discover_external_load_error_ignored(self) -> None:
        from types import SimpleNamespace

        registry = MetricRegistry()
        fake_ep = SimpleNamespace(
            name="broken_plugin",
            value="broken:Metric",
            load=lambda: (_ for _ in ()).throw(ImportError("broken")),
        )
        with patch(
            "app.evaluation.metrics.registry.importlib.metadata.entry_points",
            return_value=[fake_ep],
        ):
            discovered = registry.discover_external()
        assert discovered == []


class TestMetricRegistryToDbRecords:
    """Tests for to_db_records output format."""

    def test_to_db_records_format(self) -> None:
        registry = MetricRegistry()
        metric = _DummyMetric(name="test_db")
        registry.register(metric, plugin_module="test_pkg.mod")
        records = registry.to_db_records()
        assert len(records) == 1
        record = records[0]
        assert record["name"] == "test_db"
        assert record["category"] == "quality"
        assert record["scale"] == "binary"
        assert record["evaluator_type"] == "heuristic"
        assert record["required_inputs"] == ["prompt"]
        assert record["plugin_module"] == "test_pkg.mod"
        assert record["is_active"] is True

    def test_to_db_records_no_plugin_module(self) -> None:
        registry = MetricRegistry()
        metric = _DummyMetric(name="builtin_db")
        registry.register(metric)
        records = registry.to_db_records()
        assert records[0]["plugin_module"] is None

    def test_to_db_records_multiple(self) -> None:
        registry = MetricRegistry()
        registry.register(_DummyMetric(name="m1"))
        registry.register(_DummyMetric(name="m2"))
        registry.register(_DummyMetric(name="m3"))
        records = registry.to_db_records()
        assert len(records) == 3
        names = {r["name"] for r in records}
        assert names == {"m1", "m2", "m3"}
