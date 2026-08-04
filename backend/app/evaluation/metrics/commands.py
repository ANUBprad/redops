"""Commands and queries for the metrics engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ScoreItemCommand:
    """Command to score a single evaluation item with configured metrics."""

    run_id: str
    item_id: str
    prompt: str = ""
    response: str = ""
    reference: str = ""
    context: str = ""
    tool_calls: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    metric_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoreBatchCommand:
    """Command to score multiple items with configured metrics."""

    run_id: str
    items: tuple[ScoreItemCommand, ...] = ()


@dataclass(frozen=True, slots=True)
class GetMetricResultsQuery:
    """Query to retrieve metric results for a run."""

    run_id: str
    metric_name: str | None = None
    page: int = 1
    page_size: int = 100


@dataclass(frozen=True, slots=True)
class GetAggregatedScoresQuery:
    """Query to retrieve aggregated metric scores for a run."""

    run_id: str
    metric_name: str | None = None


@dataclass(frozen=True, slots=True)
class ListAvailableMetricsQuery:
    """Query to list all available metrics."""

    category: str | None = None


@dataclass(frozen=True, slots=True)
class GetItemMetricResultsQuery:
    """Query to retrieve metric results for a specific item."""

    run_id: str
    item_id: str
