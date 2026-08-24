"""Replay API endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.evaluation.replay.composite_repository import CompositeTraceRepository
from app.evaluation.replay.database_repository import DatabaseTraceRepository
from app.evaluation.replay.service import ItemReport, ReplayService, ReplaySummary
from app.schemas.replay import (
    ItemComparisonResponse,
    ItemReportResponse,
    MetricExplanationResponse,
    MetricSummaryResponse,
    ReplayReportResponse,
    ReplaySummaryResponse,
    TimelineEntryResponse,
    TraceComparisonResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replay", tags=["Replay"])


def _try_get_redis_fallback() -> Any:
    """Try to create a Redis trace repository for fallback.

    Returns None if Redis is not configured or unavailable.
    This allows the replay API to work without Redis when
    traces are stored in the database.
    """
    try:
        # Try to connect to Redis using the same URL from app config
        import os

        from redis import asyncio as aioredis

        from app.evaluation.replay.redis_repository import RedisTraceRepository

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        client = aioredis.from_url(redis_url, decode_responses=False)
        return RedisTraceRepository(client)
    except Exception:
        logger.debug("Redis unavailable for replay fallback, using database only")
        return None


def get_replay_service(
    session: AsyncSession = Depends(get_db_session),
) -> ReplayService:
    """Provide a replay service backed by database-primary, Redis-fallback.

    The database (evaluation_runs.trace_data) is the authoritative source
    for traces produced by the evaluation workflow. Redis is retained as
    a fallback for traces written directly by external consumers.
    """
    primary = DatabaseTraceRepository(session)
    fallback = _try_get_redis_fallback()
    return ReplayService(CompositeTraceRepository(primary, fallback))


@router.get("/traces/{run_id}", response_model=dict[str, Any])
async def get_trace(
    run_id: str,
    service: ReplayService = Depends(get_replay_service),
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the execution trace for a run."""
    trace = await service.load_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace not found for run {run_id}")
    return trace.to_dict()


@router.get("/traces/{run_id}/report", response_model=ReplayReportResponse)
async def get_replay_report(
    run_id: str,
    service: ReplayService = Depends(get_replay_service),
    _user: CurrentUser = Depends(get_current_user),
) -> ReplayReportResponse:
    """Get a detailed replay report for a run.

    Explains why each score was produced, including prompt context,
    provider responses, and metric reasoning.
    """
    trace = await service.load_trace(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace not found for run {run_id}")

    report = service.generate_replay_report(trace)

    return ReplayReportResponse(
        summary=_summary_to_response(report.summary),
        item_reports=[_item_to_response(ir) for ir in report.item_reports],
        timeline=[
            TimelineEntryResponse(
                timestamp=t.timestamp,
                event_type=t.event_type,
                sequence=t.sequence,
                duration_ms=t.duration_ms,
                data=t.data,
                error=t.error,
            )
            for t in report.timeline
        ],
        configuration=report.configuration,
    )


@router.get(
    "/compare/{baseline_run_id}/{comparison_run_id}", response_model=TraceComparisonResponse
)
async def compare_runs(
    baseline_run_id: str,
    comparison_run_id: str,
    service: ReplayService = Depends(get_replay_service),
    _user: CurrentUser = Depends(get_current_user),
) -> TraceComparisonResponse:
    """Compare two evaluation runs.

    Shows metric deltas, cost differences, latency differences,
    and determines a winner with confidence score.
    """
    baseline = await service.load_trace(baseline_run_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail=f"Baseline trace not found: {baseline_run_id}")

    comparison = await service.load_trace(comparison_run_id)
    if comparison is None:
        raise HTTPException(
            status_code=404, detail=f"Comparison trace not found: {comparison_run_id}"
        )

    result = service.compare_traces(baseline, comparison)

    return TraceComparisonResponse(
        baseline_run_id=result.baseline_run_id,
        comparison_run_id=result.comparison_run_id,
        baseline_provider=result.baseline_provider,
        comparison_provider=result.comparison_provider,
        baseline_model=result.baseline_model,
        comparison_model=result.comparison_model,
        metric_deltas=result.metric_deltas,
        cost_delta=result.cost_delta,
        latency_delta=result.latency_delta,
        item_comparisons=[
            ItemComparisonResponse(
                item_index=ic.item_index,
                metric_deltas=ic.metric_deltas,
                latency_delta=ic.latency_delta,
                cost_delta=ic.cost_delta,
            )
            for ic in result.item_comparisons
        ],
        winner=result.winner,
        confidence=result.confidence,
    )


@router.delete("/traces/{run_id}")
async def delete_trace(
    run_id: str,
    service: ReplayService = Depends(get_replay_service),
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Delete an execution trace."""
    if service._trace_repository is not None:
        deleted = await service._trace_repository.delete(run_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Trace not found: {run_id}")
    return {"status": "deleted", "run_id": run_id}


def _summary_to_response(summary: ReplaySummary) -> ReplaySummaryResponse:
    """Convert a ReplaySummary to its response model."""
    return ReplaySummaryResponse(
        run_id=summary.run_id,
        evaluation_name=summary.evaluation_name,
        provider=summary.provider,
        model=summary.model,
        status=summary.status,
        total_items=summary.total_items,
        successful_items=summary.successful_items,
        failed_items=summary.failed_items,
        total_cost_usd=summary.total_cost_usd,
        total_tokens_input=summary.total_tokens_input,
        total_tokens_output=summary.total_tokens_output,
        total_latency_ms=summary.total_latency_ms,
        metric_summaries={
            name: MetricSummaryResponse(
                metric_name=ms.metric_name,
                mean=ms.mean,
                min_score=ms.min_score,
                max_score=ms.max_score,
                count=ms.count,
            )
            for name, ms in summary.metric_summaries.items()
        },
        started_at=summary.started_at,
        completed_at=summary.completed_at,
    )


def _item_to_response(item: ItemReport) -> ItemReportResponse:
    """Convert an ItemReport to its response model."""
    return ItemReportResponse(
        item_index=item.item_index,
        prompt_preview=item.prompt_preview,
        provider_response_preview=item.provider_response_preview,
        provider_error=item.provider_error,
        metric_explanations=[
            MetricExplanationResponse(
                metric_name=me.metric_name,
                score=me.score,
                normalized_score=me.normalized_score,
                confidence=me.confidence,
                reasoning=me.reasoning,
                explanation=me.explanation,
                version=me.version,
                judge_model=me.judge_model,
            )
            for me in item.metric_explanations
        ],
        total_latency_ms=item.total_latency_ms,
        total_cost_usd=item.total_cost_usd,
        error=item.error,
    )
