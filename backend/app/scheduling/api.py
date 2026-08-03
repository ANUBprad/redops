"""Scheduling REST endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.repositories.schedule_repository import (
    SqlAlchemyScheduleRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.scheduling.schemas import CreateScheduleRequest, ScheduleResponse
from app.scheduling.services import ScheduleService

if TYPE_CHECKING:
    from app.scheduling.domain import Schedule

schedules_router = APIRouter(prefix="/schedules", tags=["schedules"])


def _get_service(session: AsyncSession) -> ScheduleService:
    return ScheduleService(SqlAlchemyScheduleRepository(session))


def _schedule_to_response(s: Schedule) -> ScheduleResponse:
    return ScheduleResponse(
        id=str(s.id),
        name=s.name,
        schedule_type=s.schedule_type.value,
        cron_expression=s.cron_expression,
        task_config=s.task_config,
        organization_id=s.organization_id,
        project_id=s.project_id,
        created_by=s.created_by,
        timezone=s.timezone,
        status=s.status.value,
        last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
        next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
        run_count=s.run_count,
        failure_count=s.failure_count,
        version=s.version,
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


@schedules_router.post("", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    body: CreateScheduleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ScheduleResponse:
    """Create a new schedule."""
    service = _get_service(session)
    try:
        schedule = await service.create_schedule(
            name=body.name,
            schedule_type=body.schedule_type,
            cron_expression=body.cron_expression,
            task_config=body.task_config,
            project_id=body.project_id,
            created_by=current_user.user_id,
            timezone=body.timezone,
        )
        return _schedule_to_response(schedule)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@schedules_router.get("", response_model=list[ScheduleResponse])
async def list_schedules(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ScheduleResponse]:
    """List active schedules."""
    service = _get_service(session)
    schedules = await service.list_active_schedules()
    return [_schedule_to_response(s) for s in schedules]


@schedules_router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ScheduleResponse:
    """Get a schedule by ID."""
    service = _get_service(session)
    try:
        schedule = await service.get_schedule(schedule_id)
        return _schedule_to_response(schedule)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@schedules_router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
async def pause_schedule(
    schedule_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ScheduleResponse:
    """Pause a schedule."""
    service = _get_service(session)
    try:
        schedule = await service.pause_schedule(schedule_id)
        return _schedule_to_response(schedule)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@schedules_router.post("/{schedule_id}/resume", response_model=ScheduleResponse)
async def resume_schedule(
    schedule_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ScheduleResponse:
    """Resume a schedule."""
    service = _get_service(session)
    try:
        schedule = await service.resume_schedule(schedule_id)
        return _schedule_to_response(schedule)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@schedules_router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a schedule."""
    service = _get_service(session)
    try:
        await service.delete_schedule(schedule_id)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
