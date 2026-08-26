"""Evaluator abstraction layer.

Provides the adapter pattern for different evaluation backends
(heuristic, embedding, LLM judge, RAGAS, custom). Metrics delegate
evaluation to the appropriate adapter based on their evaluator_type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricInput,
    MetricResult,
)


@dataclass(frozen=True, slots=True)
class EvaluatorConfig:
    """Configuration passed to an evaluator adapter."""

    provider_name: str = ""
    model: str = ""
    api_key: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class BaseEvaluatorAdapter(ABC):
    """Abstract base class for evaluator adapters.

    Each adapter wraps a specific evaluation backend and translates
    between the uniform MetricInput/MetricResult interface and the
    backend's native API.
    """

    @abstractmethod
    def evaluator_type(self) -> EvaluatorType:
        """Return the evaluator type this adapter handles."""

    @abstractmethod
    async def evaluate(
        self,
        metric_name: str,
        input_data: MetricInput,
        config: EvaluatorConfig | None = None,
    ) -> MetricResult:
        """Evaluate a metric using this adapter's backend.

        Args:
            metric_name: The metric being evaluated.
            input_data: Standardized input data.
            config: Optional evaluator-specific configuration.

        Returns:
            A MetricResult from the adapter.

        """

    async def initialize(self) -> None:  # noqa: B027
        """Optional initialization hook."""

    async def shutdown(self) -> None:  # noqa: B027
        """Optional cleanup hook."""

    def supports_metric(self, metric_name: str) -> bool:
        """Return True if this adapter supports the given metric.

        Default implementation returns True for all metrics.
        Subclasses can override for metric-specific routing.
        """
        return True


class EvaluatorRegistry:
    """Registry that maps evaluator types to adapter implementations.

    The MetricEngine uses this to dispatch metric evaluation to the
    correct adapter based on the metric's evaluator_type.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._adapters: dict[EvaluatorType, BaseEvaluatorAdapter] = {}
        self._fallback: BaseEvaluatorAdapter | None = None

    def register(
        self,
        adapter: BaseEvaluatorAdapter,
        *,
        as_fallback: bool = False,
    ) -> None:
        """Register an evaluator adapter.

        Args:
            adapter: The adapter to register.
            as_fallback: If True, use as default for unknown evaluator types.

        """
        etype = adapter.evaluator_type()
        self._adapters[etype] = adapter
        if as_fallback:
            self._fallback = adapter

    def get(self, evaluator_type: EvaluatorType) -> BaseEvaluatorAdapter | None:
        """Retrieve an adapter by evaluator type."""
        return self._adapters.get(evaluator_type)

    def get_or_fallback(
        self,
        evaluator_type: EvaluatorType,
    ) -> BaseEvaluatorAdapter | None:
        """Retrieve an adapter, falling back to the default if not found."""
        return self._adapters.get(evaluator_type) or self._fallback

    def has_adapter(self, evaluator_type: EvaluatorType) -> bool:
        """Return True if an adapter is registered for the type."""
        return evaluator_type in self._adapters

    def list_types(self) -> list[EvaluatorType]:
        """Return all registered evaluator types."""
        return list(self._adapters.keys())

    async def initialize_all(self) -> None:
        """Initialize all registered adapters."""
        for adapter in self._adapters.values():
            await adapter.initialize()

    async def shutdown_all(self) -> None:
        """Shut down all registered adapters."""
        for adapter in self._adapters.values():
            await adapter.shutdown()
