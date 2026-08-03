"""Analytics API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.domain.entities import (
    ComparisonResult,
    CostAnalysis,
    DashboardSummary,
    GeneratedReport,
    LatencyAnalysis,
    Leaderboard,
    SafetyTrend,
    TrendSeries,
)
from app.analytics.schemas.responses import (
    ActivityEntryResponse,
    ComparedItemResponse,
    ComparisonMetricResponse,
    ComparisonResultResponse,
    CostAnalysisResponse,
    DashboardSummaryResponse,
    DimensionScoreResponse,
    GeneratedReportResponse,
    LatencyAnalysisResponse,
    LeaderboardEntryResponse,
    LeaderboardResponse,
    MetricValueResponse,
    ModelCostResponse,
    ModelLatencyResponse,
    ProviderCostResponse,
    ProviderLatencyResponse,
    ReportSectionResponse,
    SafetyTrendResponse,
    TrendPointResponse,
    TrendSeriesResponse,
)
from app.core.dependencies import CurrentUser, get_current_user, get_db_session
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
from app.kernel.exceptions.errors import BaseError

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_repositories(
    session: AsyncSession,
) -> tuple[
    SqlAlchemyEvaluationRepository,
    SqlAlchemyEvaluationRunRepository,
    SqlAlchemyMetricResultRepository,
    SqlAlchemyAttackRunRepository,
]:
    """Create repositories from the database session."""
    return (
        SqlAlchemyEvaluationRepository(session),
        SqlAlchemyEvaluationRunRepository(session),
        SqlAlchemyMetricResultRepository(session),
        SqlAlchemyAttackRunRepository(session),
    )


def _dashboard_to_response(summary: DashboardSummary) -> DashboardSummaryResponse:
    """Convert domain DashboardSummary to API response."""
    activity = []
    for entry in summary.recent_activity:
        activity.append(
            ActivityEntryResponse(
                id=entry.id,
                type=entry.type,
                name=entry.name,
                status=entry.status,
                timestamp=entry.timestamp.isoformat() if entry.timestamp else None,
                summary=entry.summary,
            )
        )
    return DashboardSummaryResponse(
        total_evaluations=summary.total_evaluations,
        completed_runs=summary.completed_runs,
        success_rate=summary.success_rate,
        average_score=summary.average_score,
        average_latency_ms=summary.average_latency_ms,
        average_cost=summary.average_cost,
        total_token_usage=summary.total_token_usage,
        average_safety_score=summary.average_safety_score,
        attack_success_rate=summary.attack_success_rate,
        recent_activity=activity,
    )


def _trend_to_response(trend: TrendSeries) -> TrendSeriesResponse:
    """Convert domain TrendSeries to API response."""
    points = [
        TrendPointResponse(
            timestamp=p.timestamp.isoformat(),
            value=p.value,
            label=p.label,
        )
        for p in trend.points
    ]
    return TrendSeriesResponse(
        name=trend.name,
        points=points,
        direction=trend.direction.value
        if hasattr(trend.direction, "value")
        else str(trend.direction),
        change_percent=trend.change_percent,
    )


def _cost_to_response(cost: CostAnalysis) -> CostAnalysisResponse:
    """Convert domain CostAnalysis to API response."""
    providers = [
        ProviderCostResponse(
            provider=p.provider,
            total_cost=p.total_cost,
            run_count=p.run_count,
            average_cost_per_run=p.average_cost_per_run,
        )
        for p in cost.cost_by_provider
    ]
    models = [
        ModelCostResponse(
            model=m.model,
            provider=m.provider,
            total_cost=m.total_cost,
            run_count=m.run_count,
            average_cost_per_run=m.average_cost_per_run,
        )
        for m in cost.cost_by_model
    ]
    return CostAnalysisResponse(
        total_cost=cost.total_cost,
        average_cost_per_run=cost.average_cost_per_run,
        average_cost_per_item=cost.average_cost_per_item,
        cost_by_provider=providers,
        cost_by_model=models,
        projected_monthly_cost=cost.projected_monthly_cost,
    )


def _latency_to_response(latency: LatencyAnalysis) -> LatencyAnalysisResponse:
    """Convert domain LatencyAnalysis to API response."""
    providers = [
        ProviderLatencyResponse(
            provider=p.provider,
            average_latency_ms=p.average_latency_ms,
            run_count=p.run_count,
        )
        for p in latency.latency_by_provider
    ]
    models = [
        ModelLatencyResponse(
            model=m.model,
            provider=m.provider,
            average_latency_ms=m.average_latency_ms,
            run_count=m.run_count,
        )
        for m in latency.latency_by_model
    ]
    return LatencyAnalysisResponse(
        average_latency_ms=latency.average_latency_ms,
        median_latency_ms=latency.median_latency_ms,
        p95_latency_ms=latency.p95_latency_ms,
        p99_latency_ms=latency.p99_latency_ms,
        min_latency_ms=latency.min_latency_ms,
        max_latency_ms=latency.max_latency_ms,
        latency_by_provider=providers,
        latency_by_model=models,
    )


def _safety_to_response(safety: SafetyTrend) -> SafetyTrendResponse:
    """Convert domain SafetyTrend to API response."""
    dimensions = [
        DimensionScoreResponse(
            dimension=d.dimension,
            score=d.score,
            verdict=d.verdict,
            sample_count=d.sample_count,
        )
        for d in safety.safety_by_dimension
    ]
    return SafetyTrendResponse(
        average_safety_score=safety.average_safety_score,
        violation_rate=safety.violation_rate,
        pass_rate=safety.pass_rate,
        safety_by_dimension=dimensions,
        total_attacks=safety.total_attacks,
        total_violations=safety.total_violations,
    )


def _leaderboard_to_response(leaderboard: Leaderboard) -> LeaderboardResponse:
    """Convert domain Leaderboard to API response."""
    entries = [
        LeaderboardEntryResponse(
            rank=e.rank,
            entity_id=e.entity_id,
            entity_name=e.entity_name,
            entity_type=e.entity_type,
            score=e.score,
            metric_name=e.metric_name,
            metadata=e.metadata,
        )
        for e in leaderboard.entries
    ]
    return LeaderboardResponse(
        title=leaderboard.title,
        ranking_by=leaderboard.ranking_by,
        entries=entries,
        generated_at=leaderboard.generated_at.isoformat() if leaderboard.generated_at else None,
    )


def _comparison_to_response(comparison: ComparisonResult) -> ComparisonResultResponse:
    """Convert domain ComparisonResult to API response."""
    items = [
        ComparedItemResponse(
            entity_id=i.entity_id,
            entity_name=i.entity_name,
            entity_type=i.entity_type,
        )
        for i in comparison.compared_items
    ]
    metrics = []
    for m in comparison.metrics:
        values = [
            MetricValueResponse(
                entity_id=v.entity_id,
                value=v.value,
                formatted_value=v.formatted_value,
            )
            for v in m.values
        ]
        metrics.append(
            ComparisonMetricResponse(
                metric_name=m.metric_name,
                values=values,
                best_entity_id=m.best_entity_id,
            )
        )
    return ComparisonResultResponse(
        title=comparison.title,
        compared_items=items,
        metrics=metrics,
        summary=comparison.summary,
    )


def _report_to_response(report: GeneratedReport) -> GeneratedReportResponse:
    """Convert domain GeneratedReport to API response."""
    sections = [
        ReportSectionResponse(
            title=s.title,
            content=s.content,
            statistics=s.statistics,
        )
        for s in report.sections
    ]
    return GeneratedReportResponse(
        id=report.definition.id,
        report_type=report.definition.report_type.value,
        title=report.definition.title,
        description=report.definition.description,
        generated_at=report.definition.generated_at.isoformat()
        if report.definition.generated_at
        else None,
        summary=report.summary,
        recommendations=list(report.recommendations),
        statistics=report.statistics,
        sections=sections,
    )


@analytics_router.get("/dashboard", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    project_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardSummaryResponse:
    """Get the dashboard summary with aggregated statistics."""
    eval_repo, run_repo, metric_repo, attack_run_repo = _get_repositories(session)
    from app.analytics.services.dashboard_service import DashboardService

    service = DashboardService(
        evaluation_repo=eval_repo,
        run_repo=run_repo,
        metric_repo=metric_repo,
        attack_run_repo=attack_run_repo,
    )
    try:
        summary = await service.get_summary(project_id=project_id, days=days)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _dashboard_to_response(summary)


@analytics_router.get("/trends", response_model=TrendSeriesResponse)
async def get_historical_trends(
    metric_name: str = Query(default="score"),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    granularity: str = Query(default="day"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TrendSeriesResponse:
    """Get historical metric trends."""
    _, run_repo, metric_repo, _ = _get_repositories(session)
    from app.analytics.services.trends_service import TrendsService

    service = TrendsService(
        run_repo=run_repo,
        metric_repo=metric_repo,
    )
    try:
        trend = await service.get_metric_trend(
            metric_name=metric_name,
            project_id=project_id,
            provider=provider,
            model=model,
            days=days,
            granularity=granularity,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _trend_to_response(trend)


@analytics_router.get("/cost", response_model=CostAnalysisResponse)
async def get_cost_analysis(
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CostAnalysisResponse:
    """Get cost analysis."""
    _, run_repo, _, _ = _get_repositories(session)
    from app.analytics.services.cost_service import CostService

    service = CostService(run_repo=run_repo)
    try:
        cost = await service.get_analysis(
            project_id=project_id,
            provider=provider,
            model=model,
            days=days,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _cost_to_response(cost)


@analytics_router.get("/latency", response_model=LatencyAnalysisResponse)
async def get_latency_analysis(
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LatencyAnalysisResponse:
    """Get latency analysis."""
    _, run_repo, _, _ = _get_repositories(session)
    from app.analytics.services.latency_service import LatencyService

    service = LatencyService(run_repo=run_repo)
    try:
        latency = await service.get_analysis(
            project_id=project_id,
            provider=provider,
            model=model,
            days=days,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _latency_to_response(latency)


@analytics_router.get("/safety", response_model=SafetyTrendResponse)
async def get_safety_trend(
    project_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> SafetyTrendResponse:
    """Get safety trend analysis."""
    _, _, _, attack_run_repo = _get_repositories(session)
    from app.analytics.services.safety_service import SafetyService

    service = SafetyService(attack_run_repo=attack_run_repo)
    try:
        safety = await service.get_safety_trend(
            project_id=project_id,
            category=category,
            days=days,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _safety_to_response(safety)


@analytics_router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    ranking_by: str = Query(default="score"),
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    days: int = Query(default=30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LeaderboardResponse:
    """Get a leaderboard ranking."""
    _, run_repo, _, _ = _get_repositories(session)
    from app.analytics.services.leaderboard_service import LeaderboardService

    service = LeaderboardService(run_repo=run_repo)
    try:
        leaderboard = await service.get_leaderboard(
            ranking_by=ranking_by,
            project_id=project_id,
            provider=provider,
            limit=limit,
            days=days,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _leaderboard_to_response(leaderboard)


@analytics_router.get("/comparison", response_model=ComparisonResultResponse)
async def get_model_comparison(
    entity_type: str = Query(default="model"),
    entity_ids: str = Query(default="", description="Comma-separated entity IDs"),
    project_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ComparisonResultResponse:
    """Compare models or providers."""
    _, run_repo, metric_repo, _ = _get_repositories(session)
    from app.analytics.services.comparison_service import ComparisonService

    service = ComparisonService(
        run_repo=run_repo,
        metric_repo=metric_repo,
    )
    ids = tuple(i.strip() for i in entity_ids.split(",") if i.strip()) if entity_ids else ()
    try:
        comparison = await service.compare(
            entity_type=entity_type,
            entity_ids=ids,
            project_id=project_id,
            days=days,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _comparison_to_response(comparison)


@analytics_router.get("/reports/generate", response_model=GeneratedReportResponse)
async def generate_report(
    report_type: str = Query(default="executive_summary"),
    project_id: str | None = Query(default=None),
    evaluation_id: str | None = Query(default=None),
    run_id: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GeneratedReportResponse:
    """Generate an analytics report."""
    eval_repo, run_repo, metric_repo, attack_run_repo = _get_repositories(session)
    from app.analytics.services.comparison_service import ComparisonService
    from app.analytics.services.cost_service import CostService
    from app.analytics.services.dashboard_service import DashboardService
    from app.analytics.services.latency_service import LatencyService
    from app.analytics.services.report_service import ReportService
    from app.analytics.services.safety_service import SafetyService
    from app.analytics.services.trends_service import TrendsService

    dashboard_svc = DashboardService(
        evaluation_repo=eval_repo,
        run_repo=run_repo,
        metric_repo=metric_repo,
        attack_run_repo=attack_run_repo,
    )
    trends_svc = TrendsService(
        run_repo=run_repo,
        metric_repo=metric_repo,
    )
    cost_svc = CostService(run_repo=run_repo)
    latency_svc = LatencyService(run_repo=run_repo)
    safety_svc = SafetyService(attack_run_repo=attack_run_repo)
    comparison_svc = ComparisonService(
        run_repo=run_repo,
        metric_repo=metric_repo,
    )

    report_svc = ReportService(
        dashboard_service=dashboard_svc,
        trends_service=trends_svc,
        cost_service=cost_svc,
        latency_service=latency_svc,
        safety_service=safety_svc,
        comparison_service=comparison_svc,
    )

    try:
        report = await report_svc.generate(
            report_type=report_type,
            project_id=project_id,
            evaluation_id=evaluation_id,
            run_id=run_id,
            days=days,
            generated_by=current_user.user_id,
        )
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _report_to_response(report)
