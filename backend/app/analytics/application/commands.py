"""CQRS queries for the Analytics module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetDashboardSummaryQuery:
    """Query to retrieve the dashboard summary."""

    project_id: str | None = None
    days: int = 30


@dataclass(frozen=True, slots=True)
class GetHistoricalTrendsQuery:
    """Query to retrieve historical metric trends."""

    metric_name: str = "score"
    project_id: str | None = None
    provider: str | None = None
    model: str | None = None
    dataset_id: str | None = None
    days: int = 30
    granularity: str = "day"


@dataclass(frozen=True, slots=True)
class GetCostAnalysisQuery:
    """Query to retrieve cost analysis."""

    project_id: str | None = None
    provider: str | None = None
    model: str | None = None
    days: int = 30


@dataclass(frozen=True, slots=True)
class GetLatencyAnalysisQuery:
    """Query to retrieve latency analysis."""

    project_id: str | None = None
    provider: str | None = None
    model: str | None = None
    days: int = 30


@dataclass(frozen=True, slots=True)
class GetSafetyTrendQuery:
    """Query to retrieve safety trend analysis."""

    project_id: str | None = None
    category: str | None = None
    days: int = 30


@dataclass(frozen=True, slots=True)
class GetLeaderboardQuery:
    """Query to retrieve a leaderboard."""

    ranking_by: str = "score"
    project_id: str | None = None
    provider: str | None = None
    limit: int = 10
    days: int = 30


@dataclass(frozen=True, slots=True)
class GetModelComparisonQuery:
    """Query to compare models/providers."""

    entity_type: str = "model"
    entity_ids: tuple[str, ...] = ()
    project_id: str | None = None
    metrics: tuple[str, ...] = ()
    days: int = 30


@dataclass(frozen=True, slots=True)
class GenerateReportQuery:
    """Query to generate a report."""

    report_type: str = "executive_summary"
    project_id: str | None = None
    evaluation_id: str | None = None
    run_id: str | None = None
    days: int = 30
    generated_by: str | None = None


@dataclass(frozen=True, slots=True)
class ExportReportQuery:
    """Query to export a report."""

    report_type: str = "executive_summary"
    export_format: str = "json"
    project_id: str | None = None
    evaluation_id: str | None = None
    run_id: str | None = None
    days: int = 30
