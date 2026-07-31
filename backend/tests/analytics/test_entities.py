"""Tests for analytics domain entities."""

from __future__ import annotations

from datetime import UTC, datetime

from app.analytics.domain.entities import (
    ActivityEntry,
    ComparisonMetric,
    ComparisonResult,
    ComparedItem,
    CostAnalysis,
    DashboardSummary,
    DateRange,
    DimensionScore,
    ExportFormat,
    GeneratedReport,
    Leaderboard,
    LeaderboardEntry,
    LatencyAnalysis,
    MetricValue,
    ModelCost,
    ModelLatency,
    ProviderCost,
    ProviderLatency,
    ReportDefinition,
    ReportSection,
    ReportType,
    SafetyTrend,
    TrendDirection,
    TrendPoint,
    TrendSeries,
)


class TestDateRange:
    def test_creation(self) -> None:
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 1, 31, tzinfo=UTC)
        dr = DateRange(start=start, end=end)
        assert dr.start == start
        assert dr.end == end

    def test_immutable(self) -> None:
        dr = DateRange(
            start=datetime(2025, 1, 1, tzinfo=UTC),
            end=datetime(2025, 1, 31, tzinfo=UTC),
        )
        try:
            dr.start = datetime(2025, 2, 1, tzinfo=UTC)  # type: ignore[misc]
            assert False, "Should be immutable"
        except AttributeError:
            pass


class TestTrendDirection:
    def test_values(self) -> None:
        assert TrendDirection.UP.value == "up"
        assert TrendDirection.DOWN.value == "down"
        assert TrendDirection.FLAT.value == "flat"


class TestTrendPoint:
    def test_creation(self) -> None:
        tp = TrendPoint(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            value=0.85,
            label="test",
        )
        assert tp.value == 0.85
        assert tp.label == "test"

    def test_default_label(self) -> None:
        tp = TrendPoint(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            value=0.85,
        )
        assert tp.label == ""


class TestTrendSeries:
    def test_creation(self) -> None:
        ts = TrendSeries(
            name="score",
            points=(
                TrendPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), value=0.8),
                TrendPoint(timestamp=datetime(2025, 1, 2, tzinfo=UTC), value=0.9),
            ),
            direction=TrendDirection.UP,
            change_percent=12.5,
        )
        assert ts.name == "score"
        assert len(ts.points) == 2
        assert ts.direction == TrendDirection.UP
        assert ts.change_percent == 12.5


class TestDashboardSummary:
    def test_defaults(self) -> None:
        ds = DashboardSummary()
        assert ds.total_evaluations == 0
        assert ds.completed_runs == 0
        assert ds.success_rate == 0.0
        assert ds.recent_activity == ()

    def test_with_values(self) -> None:
        activity = (
            ActivityEntry(id="1", type="run", name="Test", status="completed"),
        )
        ds = DashboardSummary(
            total_evaluations=10,
            completed_runs=8,
            success_rate=80.0,
            recent_activity=activity,
        )
        assert ds.total_evaluations == 10
        assert len(ds.recent_activity) == 1


class TestCostAnalysis:
    def test_defaults(self) -> None:
        ca = CostAnalysis()
        assert ca.total_cost == 0.0
        assert ca.cost_by_provider == ()
        assert ca.cost_by_model == ()

    def test_with_providers(self) -> None:
        ca = CostAnalysis(
            total_cost=100.0,
            cost_by_provider=(
                ProviderCost(provider="openai", total_cost=60.0, run_count=5),
                ProviderCost(provider="anthropic", total_cost=40.0, run_count=3),
            ),
        )
        assert ca.total_cost == 100.0
        assert len(ca.cost_by_provider) == 2


class TestLatencyAnalysis:
    def test_defaults(self) -> None:
        la = LatencyAnalysis()
        assert la.average_latency_ms == 0.0
        assert la.p95_latency_ms == 0.0


class TestSafetyTrend:
    def test_defaults(self) -> None:
        st = SafetyTrend()
        assert st.average_safety_score == 0.0
        assert st.total_attacks == 0
        assert st.safety_by_dimension == ()

    def test_with_dimensions(self) -> None:
        st = SafetyTrend(
            average_safety_score=95.0,
            violation_rate=5.0,
            pass_rate=95.0,
            safety_by_dimension=(
                DimensionScore(dimension="harmlessness", score=98.0, verdict="safe"),
                DimensionScore(dimension="data_confidentiality", score=92.0, verdict="safe"),
            ),
            total_attacks=100,
            total_violations=5,
        )
        assert st.average_safety_score == 95.0
        assert len(st.safety_by_dimension) == 2


class TestLeaderboard:
    def test_defaults(self) -> None:
        lb = Leaderboard()
        assert lb.title == ""
        assert lb.entries == ()

    def test_with_entries(self) -> None:
        lb = Leaderboard(
            title="Top Models",
            ranking_by="score",
            entries=(
                LeaderboardEntry(rank=1, entity_name="gpt-4", score=95.0),
                LeaderboardEntry(rank=2, entity_name="claude-3", score=92.0),
            ),
        )
        assert lb.title == "Top Models"
        assert len(lb.entries) == 2
        assert lb.entries[0].rank == 1


class TestComparisonResult:
    def test_defaults(self) -> None:
        cr = ComparisonResult()
        assert cr.title == ""
        assert cr.compared_items == ()
        assert cr.metrics == ()

    def test_with_metrics(self) -> None:
        cr = ComparisonResult(
            title="Model Comparison",
            compared_items=(
                ComparedItem(entity_id="gpt-4", entity_name="GPT-4"),
                ComparedItem(entity_id="claude-3", entity_name="Claude 3"),
            ),
            metrics=(
                ComparisonMetric(
                    metric_name="Score",
                    values=(
                        MetricValue(entity_id="gpt-4", value=95.0, formatted_value="95.0%"),
                        MetricValue(entity_id="claude-3", value=92.0, formatted_value="92.0%"),
                    ),
                    best_entity_id="gpt-4",
                ),
            ),
        )
        assert len(cr.compared_items) == 2
        assert len(cr.metrics) == 1
        assert cr.metrics[0].best_entity_id == "gpt-4"


class TestReportType:
    def test_values(self) -> None:
        assert ReportType.EXECUTIVE_SUMMARY.value == "executive_summary"
        assert ReportType.SAFETY_REPORT.value == "safety_report"
        assert ReportType.RED_TEAM_REPORT.value == "red_team_report"


class TestExportFormat:
    def test_values(self) -> None:
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.PDF.value == "pdf"


class TestGeneratedReport:
    def test_defaults(self) -> None:
        gr = GeneratedReport()
        assert gr.definition.report_type == ReportType.EXECUTIVE_SUMMARY
        assert gr.sections == ()
        assert gr.recommendations == ()

    def test_with_sections(self) -> None:
        gr = GeneratedReport(
            definition=ReportDefinition(
                id="rpt-1",
                report_type=ReportType.EXECUTIVE_SUMMARY,
                title="Executive Summary",
            ),
            sections=(
                ReportSection(
                    title="Overview",
                    content="Test content",
                    statistics={"total": 10.0},
                ),
            ),
            summary="Test summary",
            recommendations=("Rec 1", "Rec 2"),
        )
        assert gr.definition.title == "Executive Summary"
        assert len(gr.sections) == 1
        assert len(gr.recommendations) == 2
