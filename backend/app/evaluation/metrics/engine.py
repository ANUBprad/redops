"""Metrics engine orchestrator.

Discovers, initializes, and executes metric plugins.
Provides a unified interface for scoring model outputs.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from structlog import get_logger

from app.evaluation.metrics.domain import (
    Metric,
    MetricAggregation,
    MetricDefinition,
    MetricInput,
    MetricResult,
)

if TYPE_CHECKING:
    from app.evaluation.metrics.domain import MetricCategory

logger = get_logger("redops_eval.metrics")


class MetricEngine:
    """Orchestrates metric evaluation across registered metrics.

    Manages metric lifecycle (discovery, initialization, execution)
    and provides both synchronous and asynchronous evaluation paths.
    """

    def __init__(self) -> None:
        """Initialize the engine with an empty metric registry."""
        self._metrics: dict[str, Metric] = {}
        self._definitions: dict[str, MetricDefinition] = {}
        self._initialized = False

    @property
    def initialized(self) -> bool:
        """Return True if the engine has been initialized."""
        return self._initialized

    @property
    def metric_count(self) -> int:
        """Return the number of registered metrics."""
        return len(self._metrics)

    def register(self, metric: Metric) -> None:
        """Register a metric instance.

        Args:
            metric: The metric to register.

        Raises:
            ValueError: If a metric with the same name is already registered.

        """
        defn = metric.definition()
        if defn.name in self._metrics:
            msg = f"Metric '{defn.name}' is already registered"
            raise ValueError(msg)
        self._metrics[defn.name] = metric
        self._definitions[defn.name] = defn
        logger.info("metric_registered", metric=defn.name, category=defn.category.value)

    def register_many(self, metrics: list[Metric]) -> None:
        """Register multiple metrics."""
        for metric in metrics:
            self.register(metric)

    def unregister(self, name: str) -> None:
        """Remove a metric by name."""
        self._metrics.pop(name, None)
        self._definitions.pop(name, None)

    def get(self, name: str) -> Metric | None:
        """Retrieve a metric by name."""
        return self._metrics.get(name)

    def get_all(self) -> list[Metric]:
        """Return all registered metrics."""
        return list(self._metrics.values())

    def list_definitions(self) -> list[MetricDefinition]:
        """Return definitions for all registered metrics."""
        return list(self._definitions.values())

    def list_by_category(self, category: MetricCategory) -> list[MetricDefinition]:
        """Return definitions filtered by category."""
        return [d for d in self._definitions.values() if d.category == category]

    def has_metric(self, name: str) -> bool:
        """Return True if a metric with the given name is registered."""
        return name in self._metrics

    async def initialize(self) -> None:
        """Initialize all registered metrics."""
        if self._initialized:
            return
        for name, metric in self._metrics.items():
            try:
                await metric.initialize()
                logger.info("metric_initialized", metric=name)
            except Exception:
                logger.exception("metric_init_failed", metric=name)
        self._initialized = True

    async def shutdown(self) -> None:
        """Shut down all registered metrics."""
        for name, metric in self._metrics.items():
            try:
                await metric.shutdown()
            except Exception:
                logger.exception("metric_shutdown_failed", metric=name)
        self._initialized = False

    async def evaluate_single(
        self,
        metric_name: str,
        input_data: MetricInput,
    ) -> MetricResult:
        """Evaluate a single metric against the input.

        Args:
            metric_name: Name of the metric to evaluate.
            input_data: The input data to evaluate.

        Returns:
            The MetricResult from the metric.

        Raises:
            KeyError: If the metric is not registered.

        """
        metric = self._metrics.get(metric_name)
        if metric is None:
            msg = f"Metric '{metric_name}' is not registered"
            raise KeyError(msg)

        validation_error = metric.validate_input(input_data)
        if validation_error:
            return MetricResult(
                metric_name=metric_name,
                score=0.0,
                normalized_score=0.0,
                error=validation_error,
            )

        return await metric.evaluate(input_data)

    async def evaluate_batch(
        self,
        metric_names: tuple[str, ...],
        input_data: MetricInput,
    ) -> tuple[MetricResult, ...]:
        """Evaluate multiple metrics against the same input concurrently.

        Args:
            metric_names: Names of metrics to evaluate.
            input_data: The input data to evaluate.

        Returns:
            Tuple of MetricResults in the same order as metric_names.

        """
        tasks = [self.evaluate_single(name, input_data) for name in metric_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: list[MetricResult] = []
        for name, result in zip(metric_names, results, strict=True):
            if isinstance(result, BaseException):
                output.append(
                    MetricResult(
                        metric_name=name,
                        score=0.0,
                        normalized_score=0.0,
                        error=str(result),
                    ),
                )
            else:
                output.append(result)

        return tuple(output)

    def aggregate(
        self,
        metric_name: str,
        results: tuple[MetricResult, ...],
    ) -> MetricAggregation:
        """Compute aggregated scores for a metric across results."""
        return MetricAggregation.from_results(metric_name, results)

    def resolve_metrics(
        self,
        requested: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Filter requested metric names to only those that are registered.

        Returns the intersection of requested names with registered names.
        """
        return tuple(name for name in requested if name in self._metrics)
