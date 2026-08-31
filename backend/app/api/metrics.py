"""REST endpoints for metrics engine."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.evaluation.application.commands import UpdateEvaluationCommand
from app.evaluation.application.handlers import UpdateEvaluationHandler
from app.evaluation.metrics.commands import (
    GetAggregatedScoresQuery,
    GetItemMetricResultsQuery,
    GetMetricResultsQuery,
    ListAvailableMetricsQuery,
    ScoreBatchCommand,
    ScoreItemCommand,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.handlers import (
    GetAggregatedScoresHandler,
    GetItemMetricResultsHandler,
    GetMetricResultsHandler,
    ListAvailableMetricsHandler,
    ScoreBatchHandler,
    ScoreItemHandler,
)
from app.infrastructure.database.repositories.evaluation_repository import (
    SqlAlchemyEvaluationRepository,
)
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.schemas.evaluation import EvaluationResponse
from app.schemas.metrics import (
    AggregatedScoresResponse,
    ConfigureEvaluationMetricsRequest,
    MetricAggregationResponse,
    MetricDefinitionResponse,
    MetricResultResponse,
    MetricResultsListResponse,
    ScoreBatchRequest,
    ScoreItemRequest,
)

metrics_router = APIRouter(prefix="/metrics", tags=["metrics"])

_engine: MetricEngine | None = None


def get_metric_engine() -> MetricEngine:
    """Return the global metric engine singleton."""
    global _engine
    if _engine is None:
        from app.evaluation.metrics.implementations import ALL_METRICS

        _engine = MetricEngine()
        for metric_cls in ALL_METRICS:
            _engine.register(metric_cls())
    return _engine


def _get_repository(session: AsyncSession) -> SqlAlchemyMetricResultRepository:
    """Create a repository from the database session."""
    return SqlAlchemyMetricResultRepository(session)


@metrics_router.get("", response_model=list[MetricDefinitionResponse])
async def list_metrics(
    category: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[MetricDefinitionResponse]:
    """List all available metrics, optionally filtered by category."""
    engine = get_metric_engine()
    handler = ListAvailableMetricsHandler(engine)
    query = ListAvailableMetricsQuery(category=category)
    try:
        definitions = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return [
        MetricDefinitionResponse(
            name=d.name,
            display_name=d.display_name,
            description=d.description,
            category=d.category.value,
            scale=d.scale.value,
            version=d.version,
            requires_context=d.requires_context,
            default_weight=d.default_weight,
            tags=list(d.tags),
        )
        for d in definitions
    ]


@metrics_router.post("/score", response_model=list[MetricResultResponse])
async def score_item(
    body: ScoreItemRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[MetricResultResponse]:
    """Score a single evaluation item with configured metrics."""
    engine = get_metric_engine()
    repo = _get_repository(session)
    handler = ScoreItemHandler(engine, repo)
    command = ScoreItemCommand(
        run_id=body.run_id,
        item_id=body.item_id,
        prompt=body.prompt,
        response=body.response,
        reference=body.reference,
        context=body.context,
        tool_calls=tuple(body.tool_calls),
        metadata=body.metadata,
        metric_names=tuple(body.metric_names),
    )
    try:
        results = await handler.handle(command)
        await session.flush()
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return [
        MetricResultResponse(
            metric_name=r.metric_name,
            score=r.score,
            normalized_score=r.normalized_score,
            raw_output=r.raw_output,
            reasoning=r.reasoning,
            metadata=r.metadata,
            execution_time_ms=r.execution_time_ms,
            error=r.error,
            confidence=r.confidence,
            version=r.version,
            cost_usd=r.cost_usd,
        )
        for r in results
    ]


@metrics_router.post("/score-batch", response_model=list[MetricResultResponse])
async def score_batch(
    body: ScoreBatchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[MetricResultResponse]:
    """Score multiple evaluation items with configured metrics."""
    engine = get_metric_engine()
    repo = _get_repository(session)
    score_handler = ScoreItemHandler(engine, repo)
    handler = ScoreBatchHandler(score_handler)

    items = tuple(
        ScoreItemCommand(
            run_id=item.run_id,
            item_id=item.item_id,
            prompt=item.prompt,
            response=item.response,
            reference=item.reference,
            context=item.context,
            tool_calls=tuple(item.tool_calls),
            metadata=item.metadata,
            metric_names=tuple(item.metric_names),
        )
        for item in body.items
    )
    command = ScoreBatchCommand(run_id=items[0].run_id if items else "", items=items)
    try:
        results = await handler.handle(command)
        await session.flush()
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return [
        MetricResultResponse(
            metric_name=r.metric_name,
            score=r.score,
            normalized_score=r.normalized_score,
            raw_output=r.raw_output,
            reasoning=r.reasoning,
            metadata=r.metadata,
            execution_time_ms=r.execution_time_ms,
            error=r.error,
            confidence=r.confidence,
            version=r.version,
            cost_usd=r.cost_usd,
        )
        for r in results
    ]


@metrics_router.get(
    "/runs/{run_id}/results",
    response_model=MetricResultsListResponse,
)
async def get_metric_results(
    run_id: str,
    metric_name: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MetricResultsListResponse:
    """Retrieve metric results for a run."""
    repo = _get_repository(session)
    handler = GetMetricResultsHandler(repo)
    query = GetMetricResultsQuery(
        run_id=run_id,
        metric_name=metric_name,
    )
    try:
        results = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return MetricResultsListResponse(
        items=[
            MetricResultResponse(
                metric_name=r.metric_name,
                score=r.score,
                normalized_score=r.normalized_score,
                raw_output=r.raw_output,
                reasoning=r.reasoning,
                metadata=r.metadata,
                execution_time_ms=r.execution_time_ms,
                error=r.error,
                confidence=r.confidence,
                version=r.version,
                cost_usd=r.cost_usd,
            )
            for r in results
        ],
        total=len(results),
        page=1,
        page_size=len(results) if results else 1,
        total_pages=1,
    )


@metrics_router.get(
    "/runs/{run_id}/scores",
    response_model=AggregatedScoresResponse,
)
async def get_aggregated_scores(
    run_id: str,
    metric_name: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AggregatedScoresResponse:
    """Retrieve aggregated metric scores for a run."""
    repo = _get_repository(session)
    handler = GetAggregatedScoresHandler(repo)
    query = GetAggregatedScoresQuery(
        run_id=run_id,
        metric_name=metric_name,
    )
    try:
        aggregations = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return AggregatedScoresResponse(
        run_id=run_id,
        aggregations=[
            MetricAggregationResponse(
                metric_name=a.metric_name,
                mean=a.mean,
                median=a.median,
                std_dev=a.std_dev,
                min_score=a.min_score,
                max_score=a.max_score,
                item_count=a.item_count,
                success_count=a.success_count,
                error_count=a.error_count,
                success_rate=a.success_rate,
            )
            for a in aggregations.values()
        ],
    )


@metrics_router.get(
    "/runs/{run_id}/items/{item_id}/results",
    response_model=list[MetricResultResponse],
)
async def get_item_metric_results(
    run_id: str,
    item_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[MetricResultResponse]:
    """Retrieve metric results for a specific item."""
    repo = _get_repository(session)
    handler = GetItemMetricResultsHandler(repo)
    query = GetItemMetricResultsQuery(run_id=run_id, item_id=item_id)
    try:
        results = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return [
        MetricResultResponse(
            metric_name=r.metric_name,
            score=r.score,
            normalized_score=r.normalized_score,
            raw_output=r.raw_output,
            reasoning=r.reasoning,
            metadata=r.metadata,
            execution_time_ms=r.execution_time_ms,
            error=r.error,
            confidence=r.confidence,
            version=r.version,
            cost_usd=r.cost_usd,
        )
        for r in results
    ]


@metrics_router.patch(
    "/evaluations/{evaluation_id}/enabled-metrics",
    response_model=EvaluationResponse,
)
async def configure_evaluation_metrics(
    evaluation_id: str,
    body: ConfigureEvaluationMetricsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Enable or disable metrics for an evaluation."""
    eval_repo = SqlAlchemyEvaluationRepository(session)
    handler = UpdateEvaluationHandler(eval_repo)
    command = UpdateEvaluationCommand(
        evaluation_id=evaluation_id,
        metrics=tuple(body.metric_names),
    )
    try:
        evaluation = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return EvaluationResponse(
        id=str(evaluation.id),
        project_id=evaluation.project_id,
        dataset_id=evaluation.dataset_id,
        name=str(evaluation.name.value),
        description=evaluation.description.value if evaluation.description is not None else None,
        provider=str(evaluation.provider.value),
        model=evaluation.model,
        metrics=[m.value for m in evaluation.metrics],
        tags=list(evaluation.tags),
        configuration=dict(evaluation.configuration),
        status=evaluation.status.value,
        created_by=evaluation.created_by,
        version=evaluation.version,
        created_at=evaluation.created_at.isoformat(),
        updated_at=evaluation.updated_at.isoformat(),
    )
