"""Tests for analytics CQRS commands and queries."""

from __future__ import annotations

from app.analytics.application.commands import (
    GetCostAnalysisQuery,
    GetDashboardSummaryQuery,
    GetHistoricalTrendsQuery,
    GetLatencyAnalysisQuery,
    GetLeaderboardQuery,
    GetModelComparisonQuery,
    GetSafetyTrendQuery,
    ExportReportQuery,
    GenerateReportQuery,
)


class TestGetDashboardSummaryQuery:
    def test_defaults(self) -> None:
        q = GetDashboardSummaryQuery()
        assert q.project_id is None
        assert q.days == 30

    def test_with_project(self) -> None:
        q = GetDashboardSummaryQuery(project_id="proj-1", days=7)
        assert q.project_id == "proj-1"
        assert q.days == 7

    def test_frozen(self) -> None:
        q = GetDashboardSummaryQuery()
        try:
            q.days = 60  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestGetHistoricalTrendsQuery:
    def test_defaults(self) -> None:
        q = GetHistoricalTrendsQuery()
        assert q.metric_name == "score"
        assert q.days == 30
        assert q.granularity == "day"

    def test_with_filters(self) -> None:
        q = GetHistoricalTrendsQuery(
            metric_name="cost",
            provider="openai",
            model="gpt-4",
            days=90,
            granularity="week",
        )
        assert q.metric_name == "cost"
        assert q.provider == "openai"
        assert q.model == "gpt-4"
        assert q.granularity == "week"


class TestGetCostAnalysisQuery:
    def test_defaults(self) -> None:
        q = GetCostAnalysisQuery()
        assert q.project_id is None
        assert q.days == 30

    def test_with_provider(self) -> None:
        q = GetCostAnalysisQuery(provider="anthropic", days=14)
        assert q.provider == "anthropic"
        assert q.days == 14


class TestGetLatencyAnalysisQuery:
    def test_defaults(self) -> None:
        q = GetLatencyAnalysisQuery()
        assert q.days == 30


class TestGetSafetyTrendQuery:
    def test_defaults(self) -> None:
        q = GetSafetyTrendQuery()
        assert q.days == 30
        assert q.category is None


class TestGetLeaderboardQuery:
    def test_defaults(self) -> None:
        q = GetLeaderboardQuery()
        assert q.ranking_by == "score"
        assert q.limit == 10
        assert q.days == 30

    def test_with_ranking(self) -> None:
        q = GetLeaderboardQuery(ranking_by="latency", limit=20)
        assert q.ranking_by == "latency"
        assert q.limit == 20


class TestGetModelComparisonQuery:
    def test_defaults(self) -> None:
        q = GetModelComparisonQuery()
        assert q.entity_type == "model"
        assert q.entity_ids == ()
        assert q.days == 30

    def test_with_ids(self) -> None:
        q = GetModelComparisonQuery(
            entity_type="provider",
            entity_ids=("openai", "anthropic"),
            days=14,
        )
        assert q.entity_type == "provider"
        assert len(q.entity_ids) == 2


class TestGenerateReportQuery:
    def test_defaults(self) -> None:
        q = GenerateReportQuery()
        assert q.report_type == "executive_summary"
        assert q.days == 30

    def test_with_type(self) -> None:
        q = GenerateReportQuery(report_type="safety_report", days=7)
        assert q.report_type == "safety_report"
        assert q.days == 7


class TestExportReportQuery:
    def test_defaults(self) -> None:
        q = ExportReportQuery()
        assert q.export_format == "json"
        assert q.report_type == "executive_summary"

    def test_csv(self) -> None:
        q = ExportReportQuery(export_format="csv")
        assert q.export_format == "csv"
