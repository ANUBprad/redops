"""Report generation service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.analytics.domain.entities import (
    GeneratedReport,
    ReportDefinition,
    ReportSection,
    ReportType,
)

if TYPE_CHECKING:
    from app.analytics.services.comparison_service import ComparisonService
    from app.analytics.services.cost_service import CostService
    from app.analytics.services.dashboard_service import DashboardService
    from app.analytics.services.latency_service import LatencyService
    from app.analytics.services.safety_service import SafetyService
    from app.analytics.services.trends_service import TrendsService


class ReportService:
    """Service for generating analytics reports."""

    def __init__(
        self,
        dashboard_service: DashboardService,
        trends_service: TrendsService,
        cost_service: CostService,
        latency_service: LatencyService,
        safety_service: SafetyService,
        comparison_service: ComparisonService,
    ) -> None:
        self._dashboard = dashboard_service
        self._trends = trends_service
        self._cost = cost_service
        self._latency = latency_service
        self._safety = safety_service
        self._comparison = comparison_service

    async def generate(
        self,
        report_type: str = "executive_summary",
        project_id: str | None = None,
        evaluation_id: str | None = None,
        run_id: str | None = None,
        days: int = 30,
        generated_by: str | None = None,
    ) -> GeneratedReport:
        """Generate a report of the specified type."""
        now = datetime.now(UTC)
        rt = (
            ReportType(report_type)
            if report_type in [e.value for e in ReportType]
            else ReportType.EXECUTIVE_SUMMARY
        )

        definition = ReportDefinition(
            id=f"report-{int(now.timestamp())}",
            report_type=rt,
            title=self._get_title(rt),
            description=self._get_description(rt),
            date_range=None,
            generated_at=now,
            generated_by=generated_by,
        )

        if rt == ReportType.EXECUTIVE_SUMMARY:
            sections = await self._generate_executive_summary(project_id, days)
        elif rt == ReportType.EVALUATION_REPORT:
            sections = await self._generate_evaluation_report(evaluation_id, days)
        elif rt == ReportType.RUN_REPORT:
            sections = await self._generate_run_report(run_id)
        elif rt == ReportType.SAFETY_REPORT:
            sections = await self._generate_safety_report(project_id, days)
        elif rt == ReportType.RED_TEAM_REPORT:
            sections = await self._generate_red_team_report(project_id, days)
        elif rt == ReportType.COMPARISON_REPORT:
            sections = await self._generate_comparison_report(project_id, days)
        else:
            sections = ()

        recommendations = self._generate_recommendations(rt, sections)

        statistics = {}
        for section in sections:
            statistics.update(section.statistics)

        return GeneratedReport(
            definition=definition,
            sections=sections,
            summary=self._build_summary(sections),
            recommendations=recommendations,
            statistics=statistics,
        )

    async def _generate_executive_summary(
        self,
        project_id: str | None,
        days: int,
    ) -> tuple[ReportSection, ...]:
        """Generate executive summary sections."""
        dashboard = await self._dashboard.get_summary(project_id=project_id, days=days)

        overview_stats = {
            "total_evaluations": float(dashboard.total_evaluations),
            "completed_runs": float(dashboard.completed_runs),
            "success_rate": dashboard.success_rate,
            "average_cost": dashboard.average_cost,
        }

        overview = ReportSection(
            title="Overview",
            content=(
                f"Total Evaluations: {dashboard.total_evaluations}\n"
                f"Completed Runs: {dashboard.completed_runs}\n"
                f"Success Rate: {dashboard.success_rate}%\n"
                f"Average Cost: ${dashboard.average_cost:.4f}"
            ),
            statistics=overview_stats,
        )

        cost = await self._cost.get_analysis(project_id=project_id, days=days)
        cost_section = ReportSection(
            title="Cost Analysis",
            content=(
                f"Total Cost: ${cost.total_cost:.4f}, "
                f"Projected Monthly: ${cost.projected_monthly_cost:.4f}"
            ),
            statistics={
                "total_cost": cost.total_cost,
                "projected_monthly": cost.projected_monthly_cost,
            },
        )

        safety = await self._safety.get_safety_trend(project_id=project_id, days=days)
        safety_section = ReportSection(
            title="Safety Overview",
            content=(
                f"Avg Safety Score: {safety.average_safety_score}%\n"
                f"Violation Rate: {safety.violation_rate}%\n"
                f"Total Attacks: {safety.total_attacks}"
            ),
            statistics={
                "avg_safety": safety.average_safety_score,
                "violation_rate": safety.violation_rate,
            },
        )

        return (overview, cost_section, safety_section)

    async def _generate_evaluation_report(
        self,
        evaluation_id: str | None,
        days: int,
    ) -> tuple[ReportSection, ...]:
        """Generate evaluation-specific report."""
        return (
            ReportSection(
                title="Evaluation Results",
                content=f"Report for evaluation {evaluation_id or 'all'} over {days} days",
            ),
        )

    async def _generate_run_report(
        self,
        run_id: str | None,
    ) -> tuple[ReportSection, ...]:
        """Generate run-specific report."""
        return (
            ReportSection(
                title="Run Details",
                content=f"Detailed report for run {run_id or 'all'}",
            ),
        )

    async def _generate_safety_report(
        self,
        project_id: str | None,
        days: int,
    ) -> tuple[ReportSection, ...]:
        """Generate safety-focused report."""
        safety = await self._safety.get_safety_trend(project_id=project_id, days=days)

        dim_section = ReportSection(
            title="Safety Dimensions",
            content="\n".join(
                f"{d.dimension}: {d.score}% ({d.verdict})" for d in safety.safety_by_dimension
            ),
            statistics={d.dimension: d.score for d in safety.safety_by_dimension},
        )

        return (dim_section,)

    async def _generate_red_team_report(
        self,
        project_id: str | None,
        days: int,
    ) -> tuple[ReportSection, ...]:
        """Generate red team focused report."""
        safety = await self._safety.get_safety_trend(project_id=project_id, days=days)

        return (
            ReportSection(
                title="Red Team Results",
                content=(
                    f"Total Attacks: {safety.total_attacks}\n"
                    f"Violations: {safety.total_violations}\n"
                    f"Pass Rate: {safety.pass_rate}%"
                ),
                statistics={
                    "total_attacks": float(safety.total_attacks),
                    "violations": float(safety.total_violations),
                    "pass_rate": safety.pass_rate,
                },
            ),
        )

    async def _generate_comparison_report(
        self,
        project_id: str | None,
        days: int,
    ) -> tuple[ReportSection, ...]:
        """Generate comparison report."""
        return (
            ReportSection(
                title="Model Comparison",
                content="Comparison of models across all metrics",
            ),
        )

    def _get_title(self, rt: ReportType) -> str:
        titles = {
            ReportType.EXECUTIVE_SUMMARY: "Executive Summary",
            ReportType.EVALUATION_REPORT: "Evaluation Report",
            ReportType.RUN_REPORT: "Run Report",
            ReportType.SAFETY_REPORT: "Safety Report",
            ReportType.RED_TEAM_REPORT: "Red Team Report",
            ReportType.COMPARISON_REPORT: "Comparison Report",
        }
        return titles.get(rt, "Report")

    def _get_description(self, rt: ReportType) -> str:
        descriptions = {
            ReportType.EXECUTIVE_SUMMARY: "High-level overview of platform health and key metrics",
            ReportType.EVALUATION_REPORT: "Detailed evaluation results and analysis",
            ReportType.RUN_REPORT: "Individual run performance and metrics",
            ReportType.SAFETY_REPORT: "Safety score analysis and trends",
            ReportType.RED_TEAM_REPORT: "Red team attack results and robustness analysis",
            ReportType.COMPARISON_REPORT: "Side-by-side comparison of models or providers",
        }
        return descriptions.get(rt, "")

    def _build_summary(self, sections: tuple[ReportSection, ...]) -> str:
        """Build a summary from sections."""
        if not sections:
            return "No data available for this report."
        parts = [f"{s.title}: {s.content[:200]}" for s in sections[:3]]
        return " | ".join(parts)

    def _generate_recommendations(
        self,
        rt: ReportType,
        sections: tuple[ReportSection, ...],
    ) -> tuple[str, ...]:
        """Generate actionable recommendations based on report data."""
        recommendations: list[str] = []

        for section in sections:
            stats = section.statistics
            if "violation_rate" in stats and float(str(stats["violation_rate"])) > 10:
                recommendations.append(
                    f"High violation rate ({stats['violation_rate']}%) in {section.title}. "
                    "Consider strengthening prompt safeguards."
                )
            if "total_cost" in stats and float(str(stats["total_cost"])) > 100:
                recommendations.append(
                    f"Total cost (${stats['total_cost']:.2f}) is significant. "
                    "Review model selection for cost optimization."
                )

        if not recommendations:
            recommendations.append("All metrics are within normal ranges.")

        return tuple(recommendations)
