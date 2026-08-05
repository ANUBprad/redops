"""Domain model for the metrics engine.

Defines the Metric ABC, MetricResult value object, MetricDefinition,
and supporting types for the pluggable metric framework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from typing import Any


@unique
class MetricCategory(Enum):
    """Category of metric determining execution behavior."""

    QUALITY = "quality"
    PERFORMANCE = "performance"
    COST = "cost"
    VALIDATION = "validation"
    COMPOSITE = "composite"


@unique
class MetricScale(Enum):
    """Scale type for metric scores."""

    BINARY = "binary"
    CONTINUOUS = "continuous"
    RANKING = "ranking"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Declarative definition of a metric's capabilities."""

    name: str
    display_name: str
    description: str
    category: MetricCategory
    scale: MetricScale
    version: str = "1.0.0"
    requires_context: bool = False
    default_weight: float = 1.0
    tags: tuple[str, ...] = ()

    @property
    def is_quality_metric(self) -> bool:
        """Return True if this is a quality metric."""
        return self.category == MetricCategory.QUALITY

    @property
    def is_performance_metric(self) -> bool:
        """Return True if this is a performance metric."""
        return self.category == MetricCategory.PERFORMANCE


@dataclass(frozen=True, slots=True)
class MetricInput:
    """Input data for metric evaluation."""

    prompt: str = ""
    response: str = ""
    reference: str = ""
    context: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MetricResult:
    """Result of a single metric evaluation.

    Persisted to the database for retrieval and aggregation.
    """

    metric_name: str
    score: float
    normalized_score: float
    raw_output: str = ""
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    error: str | None = None
    created_at: datetime | None = None
    confidence: float = 0.0
    version: str = "1.0.0"
    cost_usd: float = 0.0

    @property
    def is_success(self) -> bool:
        """Return True if the metric computed without error."""
        return self.error is None

    @property
    def is_valid_score(self) -> bool:
        """Return True if the normalized score is in [0.0, 1.0]."""
        return 0.0 <= self.normalized_score <= 1.0


@dataclass(frozen=True, slots=True)
class MetricAggregation:
    """Aggregated metric scores across multiple items."""

    metric_name: str
    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    item_count: int = 0
    success_count: int = 0
    error_count: int = 0

    @property
    def success_rate(self) -> float:
        """Return the ratio of successful evaluations."""
        if self.item_count == 0:
            return 0.0
        return self.success_count / self.item_count

    @classmethod
    def from_results(
        cls,
        metric_name: str,
        results: tuple[MetricResult, ...],
    ) -> MetricAggregation:
        """Compute aggregation from a collection of metric results."""
        if not results:
            return cls(metric_name=metric_name)

        scores = [r.normalized_score for r in results if r.is_success]
        success_count = sum(1 for r in results if r.is_success)
        error_count = len(results) - success_count

        if not scores:
            return cls(
                metric_name=metric_name,
                item_count=len(results),
                success_count=success_count,
                error_count=error_count,
            )

        import statistics

        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        median = (
            sorted_scores[n // 2]
            if n % 2 == 1
            else (sorted_scores[n // 2 - 1] + sorted_scores[n // 2]) / 2
        )

        return cls(
            metric_name=metric_name,
            mean=statistics.mean(scores),
            median=median,
            std_dev=statistics.stdev(scores) if len(scores) > 1 else 0.0,
            min_score=min(scores),
            max_score=max(scores),
            item_count=len(results),
            success_count=success_count,
            error_count=error_count,
        )


class Metric(ABC):
    """Abstract base class for all metrics.

    Every metric must implement this interface to be discoverable
    and injectable by the MetricsEngine.
    """

    @abstractmethod
    def definition(self) -> MetricDefinition:
        """Return the metric's declarative definition."""

    @abstractmethod
    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate the metric against the provided input.

        Args:
            input_data: The prompt, response, and context to evaluate.

        Returns:
            A MetricResult with score, reasoning, and metadata.

        """

    async def initialize(self) -> None:  # noqa: B027
        """Optional initialization hook called once at startup."""

    async def shutdown(self) -> None:  # noqa: B027
        """Optional cleanup hook called at shutdown."""

    def validate_input(self, input_data: MetricInput) -> str | None:
        """Validate input data before evaluation.

        Returns:
            An error message if validation fails, or None if valid.

        """
        return None
