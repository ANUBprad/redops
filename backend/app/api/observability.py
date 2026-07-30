"""REST + SSE endpoints for run observability."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.api.schemas.observability import (
    LogEntryCreateRequest,
    LogEntryResponse,
    PaginatedLogsResponse,
    PaginatedTimelineResponse,
    TimelineEventResponse,
)
from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.evaluation.observability.broadcaster import get_broadcaster
from app.evaluation.observability.domain import RunLogEntry
from app.infrastructure.database.repositories.run_event_repository import (
    SqlAlchemyRunEventRepository,
)
from app.infrastructure.database.repositories.run_log_repository import (
    SqlAlchemyRunLogRepository,
)
from app.kernel.entities.base import UUIDv7

observability_router = APIRouter(prefix="/runs", tags=["observability"])


async def _sse_generator(run_id: str, request: Request, *, progress_only: bool = False) -> Any:
    broadcaster = get_broadcaster()
    async for event in broadcaster.stream(run_id):
        if await request.is_disconnected():
            break
        if progress_only and not event.get("event_type", "").startswith("evaluation."):
            continue
        yield f"event: {event.get('event_type', 'message')}\ndata: {json.dumps(event, default=str)}\n\n"


def _get_timeline_repo(
    session: AsyncSession,
) -> SqlAlchemyRunEventRepository:
    return SqlAlchemyRunEventRepository(session)


def _get_log_repo(
    session: AsyncSession,
) -> SqlAlchemyRunLogRepository:
    return SqlAlchemyRunLogRepository(session)


@observability_router.get(
    "/{run_id}/events",
    response_model=PaginatedTimelineResponse,
)
async def get_run_timeline(
    run_id: str,
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedTimelineResponse:
    r_id = _parse_run_id(run_id)
    repo = _get_timeline_repo(session)
    items = await repo.find_by_run_id(r_id, event_type=event_type, limit=limit, offset=offset)
    total = await repo.count_by_run_id(r_id)
    return PaginatedTimelineResponse(
        items=[
            TimelineEventResponse(
                event_id=str(e.entry_id),
                run_id=str(e.run_id),
                event_type=e.event_type,
                data=e.data,
                correlation_id=e.correlation_id,
                occurred_at=e.occurred_at,
            )
            for e in items
        ],
        total=total,
    )


@observability_router.get("/{run_id}/events/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    r_id = _parse_run_id(run_id)
    return StreamingResponse(
        _sse_generator(str(r_id), request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@observability_router.get("/{run_id}/progress/stream")
async def stream_run_progress(
    run_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    r_id = _parse_run_id(run_id)
    return StreamingResponse(
        _sse_generator(str(r_id), request, progress_only=True),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@observability_router.post("/{run_id}/logs", status_code=201)
async def create_run_log(
    run_id: str,
    body: LogEntryCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LogEntryResponse:
    r_id = _parse_run_id(run_id)
    repo = _get_log_repo(session)
    entry = RunLogEntry(
        run_id=r_id,
        level=body.level,
        source=body.source,
        message=body.message,
        metadata=body.metadata,
        correlation_id=body.correlation_id,
    )
    await repo.save(entry)
    await session.flush()

    response = LogEntryResponse(
        log_id=str(entry.log_id),
        run_id=str(entry.run_id),
        level=entry.level,
        source=entry.source,
        message=entry.message,
        metadata=entry.metadata,
        correlation_id=entry.correlation_id,
        timestamp=entry.timestamp,
    )
    broadcaster = get_broadcaster()
    await broadcaster.publish(
        str(r_id),
        {
            "event_type": "run.log",
            "occurred_at": entry.timestamp.isoformat(),
            "data": response.model_dump(mode="json"),
        },
    )
    return response


@observability_router.get("/{run_id}/logs", response_model=PaginatedLogsResponse)
async def get_run_logs(
    run_id: str,
    level: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedLogsResponse:
    r_id = _parse_run_id(run_id)
    repo = _get_log_repo(session)
    items = await repo.find_by_run_id(r_id, level=level, source=source, limit=limit, offset=offset)
    total = await repo.count_by_run_id(r_id, level=level)
    return PaginatedLogsResponse(
        items=[
            LogEntryResponse(
                log_id=str(e.log_id),
                run_id=str(e.run_id),
                level=e.level,
                source=e.source,
                message=e.message,
                metadata=e.metadata,
                correlation_id=e.correlation_id,
                timestamp=e.timestamp,
            )
            for e in items
        ],
        total=total,
    )


def _parse_run_id(run_id: str) -> UUIDv7:
    try:
        return UUIDv7.from_string(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid run_id: {run_id}") from None
