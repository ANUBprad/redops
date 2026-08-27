"""MetricRegistry — metric discovery, registration, and version traceability.

Discovers built-in and external plugin metrics, validates them,
and populates the metric_definitions database table for version
traceability. This is the single source of truth for what metrics
are available in the system.
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from structlog import get_logger

from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricScale,
)

logger = get_logger("redops_eval.metrics.registry")

ENTRY_POINT_GROUP = "redops.metrics"


class MetricRegistry:
    """Registry that discovers, validates, and manages all metric plugins.

    On construction, loads built-in metrics from the provided list.
    External plugin metrics are discovered via
    ``importlib.metadata.entry_points(group="redops.metrics")``.

    Each metric plugin is validated before registration: it must be a
    subclass of ``Metric``, implement ``definition()``, and have a
    unique name not already registered.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._metrics: dict[str, Metric] = {}
        self._definitions: dict[str, MetricDefinition] = {}
        self._plugin_modules: dict[str, str] = {}

    @property
    def metric_count(self) -> int:
        """Return the number of registered metrics."""
        return len(self._metrics)

    def register(self, metric: Metric, *, plugin_module: str | None = None) -> None:
        """Register a metric instance.

        Args:
            metric: The metric to register.
            plugin_module: Optional Python module path for plugin metrics.

        Raises:
            ValueError: If the metric name is already registered or
                the metric fails validation.

        """
        defn = metric.definition()
        self._validate_metric(metric, defn)
        if defn.name in self._metrics:
            msg = f"Metric '{defn.name}' is already registered"
            raise ValueError(msg)
        self._metrics[defn.name] = metric
        self._definitions[defn.name] = defn
        if plugin_module:
            self._plugin_modules[defn.name] = plugin_module
        logger.info(
            "metric_registered",
            metric=defn.name,
            version=defn.version,
            evaluator_type=defn.evaluator_type.value,
            plugin=plugin_module or "builtin",
        )  # type: ignore[call-arg]

    def register_many(
        self,
        metrics: list[Metric],
        *,
        plugin_module: str | None = None,
    ) -> None:
        """Register multiple metrics."""
        for metric in metrics:
            self.register(metric, plugin_module=plugin_module)

    def register_builtin(self, metrics: list[Metric]) -> None:
        """Register built-in metrics (no plugin module)."""
        self.register_many(metrics)

    def get(self, name: str) -> Metric | None:
        """Retrieve a metric by name."""
        return self._metrics.get(name)

    def get_definition(self, name: str) -> MetricDefinition | None:
        """Retrieve a metric definition by name."""
        return self._definitions.get(name)

    def get_all(self) -> list[Metric]:
        """Return all registered metrics."""
        return list(self._metrics.values())

    def list_definitions(self) -> list[MetricDefinition]:
        """Return definitions for all registered metrics."""
        return list(self._definitions.values())

    def list_by_category(
        self,
        category: MetricCategory,
    ) -> list[MetricDefinition]:
        """Return definitions filtered by category."""
        return [d for d in self._definitions.values() if d.category == category]

    def list_by_evaluator_type(
        self,
        evaluator_type: EvaluatorType,
    ) -> list[MetricDefinition]:
        """Return definitions filtered by evaluator type."""
        return [
            d for d in self._definitions.values()
            if d.evaluator_type == evaluator_type
        ]

    def list_plugin_metrics(self) -> list[MetricDefinition]:
        """Return definitions for plugin-provided metrics only."""
        return [d for d in self._definitions.values() if d.name in self._plugin_modules]

    def has_metric(self, name: str) -> bool:
        """Return True if a metric with the given name is registered."""
        return name in self._metrics

    def discover_external(self) -> list[str]:
        """Discover and register external metric plugins via entry points.

        Scans the ``redops.metrics`` entry point group. Each entry point
        must resolve to a ``Metric`` subclass (not an instance). The class
        is instantiated and registered.

        Returns:
            List of metric names that were successfully discovered and
            registered.

        """
        discovered: list[str] = []
        try:
            eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
        except Exception:
            logger.exception("entry_point_discovery_failed")
            return discovered

        for ep in eps:
            try:
                metric_cls = ep.load()
                if not (isinstance(metric_cls, type) and issubclass(metric_cls, Metric)):
                    logger.warning(
                        "entry_point_not_metric",
                        entry_point=ep.name,
                        type=type(metric_cls).__name__,
                    )  # type: ignore[call-arg]
                    continue
                metric_instance = metric_cls()
                defn = metric_instance.definition()
                plugin_module = ep.value.split(":")[0] if ":" in ep.value else ep.value
                self.register(metric_instance, plugin_module=plugin_module)
                discovered.append(defn.name)
                logger.info(
                    "plugin_metric_discovered",
                    metric=defn.name,
                    entry_point=ep.name,
                    version=defn.version,
                )  # type: ignore[call-arg]
            except Exception:
                logger.exception(
                    "plugin_metric_load_failed",
                    entry_point=ep.name,
                )  # type: ignore[call-arg]

        return discovered

    def to_db_records(self) -> list[dict[str, Any]]:
        """Export all definitions as dictionaries for DB persistence.

        Returns:
            List of dictionaries matching the metric_definitions table
            schema, ready for bulk upsert.

        """
        records: list[dict[str, Any]] = []
        for name, defn in self._definitions.items():
            records.append({
                "name": defn.name,
                "display_name": defn.display_name,
                "description": defn.description,
                "category": defn.category.value,
                "scale": defn.scale.value,
                "version": defn.version,
                "evaluator_type": defn.evaluator_type.value,
                "required_inputs": list(defn.required_inputs),
                "default_weight": defn.default_weight,
                "direction": defn.direction.value,
                "default_threshold": defn.default_threshold,
                "requires_context": defn.requires_context,
                "plugin_module": self._plugin_modules.get(name),
                "tags": list(defn.tags),
                "is_active": True,
            })
        return records

    def _validate_metric(self, metric: Metric, defn: MetricDefinition) -> None:
        """Validate a metric before registration.

        Raises:
            ValueError: If the metric fails validation.

        """
        if not isinstance(metric, Metric):
            msg = f"Expected Metric instance, got {type(metric).__name__}"
            raise ValueError(msg)
        if not defn.name:
            msg = "Metric definition must have a non-empty name"
            raise ValueError(msg)
        if not defn.display_name:
            msg = f"Metric '{defn.name}' must have a non-empty display_name"
            raise ValueError(msg)
        if not isinstance(defn.category, MetricCategory):
            msg = f"Metric '{defn.name}' has invalid category: {defn.category}"
            raise ValueError(msg)
        if not isinstance(defn.scale, MetricScale):
            msg = f"Metric '{defn.name}' has invalid scale: {defn.scale}"
            raise ValueError(msg)
        if not isinstance(defn.evaluator_type, EvaluatorType):
            msg = f"Metric '{defn.name}' has invalid evaluator_type: {defn.evaluator_type}"
            raise ValueError(msg)
        if not defn.required_inputs:
            msg = f"Metric '{defn.name}' must declare at least one required_input"
            raise ValueError(msg)
        if defn.version and not all(
            c.isdigit() or c == "." for c in defn.version
        ):
            msg = f"Metric '{defn.name}' has invalid version format: {defn.version}"
            raise ValueError(msg)
