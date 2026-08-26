"""Temporal activities for report generation and export.

Delegates to ReportService and ExportService for the heavy lifting.
Uses module-level globals configured during worker startup for
dependency resolution, following the same pattern as evaluation activities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from temporalio import activity

from app.analytics.services.export_service import ExportService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_export_session_factory(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Set the session factory for export activities.

    Called once during worker startup.
    """
    global _session_factory
    _session_factory = factory


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        msg = "Session factory not configured. Call configure_export_session_factory first."
        raise RuntimeError(msg)
    return _session_factory


# ---------------------------------------------------------------------------
# Activity input / output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GenerateExportInput:
    """Input for the generate-export activity.

    Attributes:
        report_type: Type of report to generate (executive_summary, etc.).
        project_id: Optional project ID filter.
        evaluation_id: Optional evaluation ID filter.
        run_id: Optional run ID filter.
        days: Lookback window in days.
        export_format: Export format (json, csv, pdf).
        generated_by: User ID who requested the export.

    """

    report_type: str = "executive_summary"
    project_id: str = ""
    evaluation_id: str = ""
    run_id: str = ""
    days: int = 30
    export_format: str = "json"
    generated_by: str = ""


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Result of the export activity."""

    report_type: str = ""
    export_format: str = ""
    content: str = ""
    section_count: int = 0
    title: str = ""


# ---------------------------------------------------------------------------
# Activity implementation
# ---------------------------------------------------------------------------


@activity.defn
async def generate_export_activity(input: GenerateExportInput) -> ExportResult:
    """Generate a report and export it in the requested format.

    This activity runs inside Temporal, so HTTP timeouts are not a concern.
    Large report generation (many runs, many metrics) can take minutes
    without risk of client disconnection.

    Each activity invocation creates its own database session via the
    configured session factory.
    """
    factory = _get_session_factory()

    async with factory() as session:
        from app.analytics.services.comparison_service import ComparisonService
        from app.analytics.services.cost_service import CostService
        from app.analytics.services.dashboard_service import DashboardService
        from app.analytics.services.latency_service import LatencyService
        from app.analytics.services.report_service import ReportService
        from app.analytics.services.safety_service import SafetyService
        from app.analytics.services.trends_service import TrendsService
        from app.infrastructure.database.repositories.attack_run_repository import (
            SqlAlchemyAttackRunRepository,
        )
        from app.infrastructure.database.repositories.evaluation_repository import (
            SqlAlchemyEvaluationRepository,
        )
        from app.infrastructure.database.repositories.evaluation_run_repository import (
            SqlAlchemyEvaluationRunRepository,
        )
        from app.infrastructure.database.repositories.metric_result_repository import (
            SqlAlchemyMetricResultRepository,
        )

        eval_repo = SqlAlchemyEvaluationRepository(session)
        run_repo = SqlAlchemyEvaluationRunRepository(session)
        metric_repo = SqlAlchemyMetricResultRepository(session)
        attack_repo = SqlAlchemyAttackRunRepository(session)

        dashboard_svc = DashboardService(
            evaluation_repo=eval_repo,
            run_repo=run_repo,
            metric_repo=metric_repo,
            attack_run_repo=attack_repo,
        )
        trends_svc = TrendsService(run_repo=run_repo, metric_repo=metric_repo)
        cost_svc = CostService(run_repo=run_repo)
        latency_svc = LatencyService(run_repo=run_repo)
        safety_svc = SafetyService(attack_run_repo=attack_repo)
        comparison_svc = ComparisonService(run_repo=run_repo, metric_repo=metric_repo)

        report_svc = ReportService(
            dashboard_service=dashboard_svc,
            trends_service=trends_svc,
            cost_service=cost_svc,
            latency_service=latency_svc,
            safety_service=safety_svc,
            comparison_service=comparison_svc,
        )

        report = await report_svc.generate(
            report_type=input.report_type,
            project_id=input.project_id or None,
            evaluation_id=input.evaluation_id or None,
            run_id=input.run_id or None,
            days=input.days,
            generated_by=input.generated_by,
        )

        export_svc = ExportService()
        content = await export_svc.export(report, format=input.export_format)

    return ExportResult(
        report_type=input.report_type,
        export_format=input.export_format,
        content=content,
        section_count=len(report.sections),
        title=report.definition.title,
    )
