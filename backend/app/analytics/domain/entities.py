"""Domain entities for the Analytics module.

These are read-model entities computed from existing evaluation,
run, metric, and red-team data. They do not persist independently;
they are derived from queries against existing repositories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TrendDirection(str, Enum):
    """Direction of a trend."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class LeaderboardRanking(str, Enum):
    """Leaderboard sort direction."""

    BEST = "best"
    WORST = "worst"


class ReportType(str, Enum):
    """Types of reports that can be generated."""

    EXECUTIVE_SUMMARY = "executive_summary"
    EVALUATION_REPORT = "evaluation_report"
    RUN_REPORT = "run_report"
    SAFETY_REPORT = "safety_report"
    RED_TEAM_REPORT = "red_team_report"
    COMPARISON_REPORT = "comparison_report"


class ExportFormat(str, Enum):
    """Export format options."""

    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


@dataclass(frozen=True)
class DateRange:
    """Immutable date range filter."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class TrendPoint:
    """A single point in a time-series trend."""

    timestamp: datetime
    value: float
    label: str = ""


@dataclass(frozen=True)
class TrendSeries:
    """A named time-series with direction indicator."""

    name: str
    points: tuple[TrendPoint, ...] = ()
    direction: TrendDirection = TrendDirection.FLAT
    change_percent: float = 0.0


@dataclass(frozen=True)
class ActivityEntry:
    """A single recent activity item."""

    id: str = ""
    type: str = ""
    name: str = ""
    status: str = ""
    timestamp: datetime | None = None
    summary: str = ""


@dataclass(frozen=True)
class DashboardSummary:
    """Aggregated dashboard statistics."""

    total_evaluations: int = 0
    completed_runs: int = 0
    success_rate: float = 0.0
    average_score: float = 0.0
    average_latency_ms: float = 0.0
    average_cost: float = 0.0
    total_token_usage: int = 0
    average_safety_score: float = 0.0
    attack_success_rate: float = 0.0
    recent_activity: tuple[ActivityEntry, ...] = ()


@dataclass(frozen=True)
class CostAnalysis:
    """Cost analysis breakdown."""

    total_cost: float = 0.0
    average_cost_per_run: float = 0.0
    average_cost_per_item: float = 0.0
    cost_by_provider: tuple[ProviderCost, ...] = ()
    cost_by_model: tuple[ModelCost, ...] = ()
    cost_trend: TrendSeries | None = None
    projected_monthly_cost: float = 0.0


@dataclass(frozen=True)
class ProviderCost:
    """Cost breakdown by provider."""

    provider: str
    total_cost: float = 0.0
    run_count: int = 0
    average_cost_per_run: float = 0.0


@dataclass(frozen=True)
class ModelCost:
    """Cost breakdown by model."""

    model: str
    provider: str = ""
    total_cost: float = 0.0
    run_count: int = 0
    average_cost_per_run: float = 0.0


@dataclass(frozen=True)
class LatencyAnalysis:
    """Latency analysis breakdown."""

    average_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    latency_by_provider: tuple[ProviderLatency, ...] = ()
    latency_by_model: tuple[ModelLatency, ...] = ()
    latency_trend: TrendSeries | None = None


@dataclass(frozen=True)
class ProviderLatency:
    """Latency breakdown by provider."""

    provider: str
    average_latency_ms: float = 0.0
    run_count: int = 0


@dataclass(frozen=True)
class ModelLatency:
    """Latency breakdown by model."""

    model: str
    provider: str = ""
    average_latency_ms: float = 0.0
    run_count: int = 0


@dataclass(frozen=True)
class SafetyTrend:
    """Safety score trend analysis."""

    average_safety_score: float = 0.0
    violation_rate: float = 0.0
    pass_rate: float = 0.0
    safety_by_dimension: tuple[DimensionScore, ...] = ()
    safety_trend: TrendSeries | None = None
    total_attacks: int = 0
    total_violations: int = 0


@dataclass(frozen=True)
class DimensionScore:
    """Safety score for a specific dimension."""

    dimension: str
    score: float = 0.0
    verdict: str = ""
    sample_count: int = 0


@dataclass(frozen=True)
class LeaderboardEntry:
    """A single entry in a leaderboard."""

    rank: int = 0
    entity_id: str = ""
    entity_name: str = ""
    entity_type: str = ""
    score: float = 0.0
    metric_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Leaderboard:
    """A ranked leaderboard."""

    title: str = ""
    ranking_by: str = ""
    entries: tuple[LeaderboardEntry, ...] = ()
    generated_at: datetime | None = None


@dataclass(frozen=True)
class ComparisonResult:
    """Result of comparing two or more entities."""

    title: str = ""
    compared_items: tuple[ComparedItem, ...] = ()
    metrics: tuple[ComparisonMetric, ...] = ()
    summary: str = ""


@dataclass(frozen=True)
class ComparedItem:
    """A single item being compared."""

    entity_id: str = ""
    entity_name: str = ""
    entity_type: str = ""


@dataclass(frozen=True)
class ComparisonMetric:
    """A metric value for comparison across items."""

    metric_name: str = ""
    values: tuple[MetricValue, ...] = ()
    best_entity_id: str = ""


@dataclass(frozen=True)
class MetricValue:
    """A metric value for a specific entity."""

    entity_id: str = ""
    value: float = 0.0
    formatted_value: str = ""


@dataclass(frozen=True)
class ReportDefinition:
    """Definition of a generated report."""

    id: str = ""
    report_type: ReportType = ReportType.EXECUTIVE_SUMMARY
    title: str = ""
    description: str = ""
    date_range: DateRange | None = None
    filters: dict[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None
    generated_by: str | None = None


@dataclass(frozen=True)
class ReportSection:
    """A section within a report."""

    title: str = ""
    content: str = ""
    charts: tuple[ReportChart, ...] = ()
    statistics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportChart:
    """Chart data embedded in a report."""

    chart_type: str = ""
    title: str = ""
    data: tuple[TrendPoint, ...] = ()


@dataclass(frozen=True)
class GeneratedReport:
    """A fully generated report with all sections."""

    definition: ReportDefinition = field(default_factory=ReportDefinition)
    sections: tuple[ReportSection, ...] = ()
    summary: str = ""
    recommendations: tuple[str, ...] = ()
    statistics: dict[str, float] = field(default_factory=dict)
