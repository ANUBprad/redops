"""Composite metric implementations.

Provides metrics that combine results from multiple sub-metrics
using configurable aggregation strategies (average, weighted, custom).
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any

from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)


@dataclass(frozen=True, slots=True)
class CompositeComponent:
    """A component metric within a composite metric.

    Attributes:
        metric_name: Name of the sub-metric.
        weight: Weight for weighted aggregation (default 1.0).

    """

    metric_name: str
    weight: float = 1.0


class CompositeMetric(Metric):
    """Abstract base class for composite metrics.

    A composite metric combines results from multiple sub-metrics
    into a single score. Subclasses define the aggregation strategy.
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        components: list[CompositeComponent],
    ) -> None:
        """Initialize with component metrics.

        Args:
            name: Unique name for this composite metric.
            display_name: Human-readable display name.
            description: Description of the composite metric.
            components: List of sub-metrics to combine.

        """
        self._name = name
        self._display_name = display_name
        self._description = description
        self._components = tuple(components)

    @property
    def components(self) -> tuple[CompositeComponent, ...]:
        """Return the component metrics."""
        return self._components

    def definition(self) -> MetricDefinition:
        """Return the composite metric definition."""
        return MetricDefinition(
            name=self._name,
            display_name=self._display_name,
            description=self._description,
            category=MetricCategory.COMPOSITE,
            scale=MetricScale.CONTINUOUS,
            evaluator_type=EvaluatorType.CUSTOM,
            required_inputs=("prompt", "response"),
            tags=("composite",),
        )

    @abstractmethod
    def aggregate_scores(
        self,
        component_results: dict[str, MetricResult],
    ) -> float:
        """Aggregate component scores into a single score.

        Args:
            component_results: Mapping of metric_name → MetricResult
                for each component.

        Returns:
            The aggregated score.

        """

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate a composite metric.

        This method should NOT be called directly. Composite metrics
        require access to the MetricEngine to evaluate sub-metrics.
        Use ``evaluate_with_engine`` instead.
        """
        msg = (
            f"CompositeMetric '{self._name}' requires the MetricEngine. "
            "Use evaluate_with_engine() instead."
        )
        raise NotImplementedError(msg)

    async def evaluate_with_engine(
        self,
        input_data: MetricInput,
        engine: Any,
    ) -> MetricResult:
        """Evaluate using the MetricEngine to resolve sub-metrics.

        Args:
            input_data: The input data to evaluate.
            engine: The MetricEngine instance.

        Returns:
            A MetricResult with the aggregated score.

        """
        import time

        start = time.monotonic()
        component_results: dict[str, MetricResult] = {}

        for component in self._components:
            try:
                result = await engine.evaluate_single(
                    component.metric_name,
                    input_data,
                )
                component_results[component.metric_name] = result
            except KeyError:
                component_results[component.metric_name] = MetricResult(
                    metric_name=component.metric_name,
                    score=0.0,
                    normalized_score=0.0,
                    error=f"Component metric '{component.metric_name}' not registered",
                )

        # Check if all components failed
        all_failed = all(not r.is_success for r in component_results.values())
        if all_failed:
            return MetricResult(
                metric_name=self._name,
                score=0.0,
                normalized_score=0.0,
                error="All component metrics failed",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            aggregated_score = self.aggregate_scores(component_results)
        except Exception as e:
            return MetricResult(
                metric_name=self._name,
                score=0.0,
                normalized_score=0.0,
                error=f"Aggregation failed: {e}",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        # Build reasoning from component results
        reasoning_parts = []
        for name, result in component_results.items():
            status = "OK" if result.is_success else f"ERR: {result.error}"
            reasoning_parts.append(f"{name}={result.normalized_score:.3f} ({status})")

        return MetricResult(
            metric_name=self._name,
            score=aggregated_score,
            normalized_score=min(max(aggregated_score, 0.0), 1.0),
            reasoning="; ".join(reasoning_parts),
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            metadata={
                "component_results": {
                    name: {"score": r.score, "normalized_score": r.normalized_score}
                    for name, r in component_results.items()
                }
            },
        )


class AverageCompositeMetric(CompositeMetric):
    """Composite metric that computes a simple average of component scores."""

    def aggregate_scores(
        self,
        component_results: dict[str, MetricResult],
    ) -> float:
        successful = [r.normalized_score for r in component_results.values() if r.is_success]
        if not successful:
            return 0.0
        return sum(successful) / len(successful)


class WeightedCompositeMetric(CompositeMetric):
    """Composite metric that computes a weighted average of component scores.

    Weights are taken from the CompositeComponent.weight field.
    """

    def aggregate_scores(
        self,
        component_results: dict[str, MetricResult],
    ) -> float:
        weighted_sum = 0.0
        total_weight = 0.0

        for component in self._components:
            result = component_results.get(component.metric_name)
            if result is not None and result.is_success:
                weighted_sum += result.normalized_score * component.weight
                total_weight += component.weight

        if total_weight == 0.0:
            return 0.0
        return weighted_sum / total_weight
