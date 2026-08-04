"""Audit REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.schemas.responses import AuditLogListResponse, AuditLogResponse
from app.audit.services.audit_service import AuditService
from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.repositories.audit_repository import (
    SqlAlchemyAuditLogRepository,
)

audit_router = APIRouter(prefix="/audit", tags=["audit"])


def _get_service(session: AsyncSession) -> AuditService:
    return AuditService(SqlAlchemyAuditLogRepository(session))


def _log_to_response(entry: object) -> AuditLogResponse:
    from app.audit.domain.entities import AuditLog

    e = entry if isinstance(entry, AuditLog) else AuditLog()
    return AuditLogResponse(
        log_id=e.log_id,
        user_id=e.user_id,
        user_email=e.user_email,
        action=e.action,
        resource_type=e.resource_type,
        resource_id=e.resource_id,
        organization_id=e.organization_id,
        ip_address=e.ip_address,
        user_agent=e.user_agent,
        metadata=e.metadata,
        timestamp=e.timestamp.isoformat(),
        request_id=e.request_id,
    )


@audit_router.get("/{org_id}", response_model=AuditLogListResponse)
async def list_audit_logs(
    org_id: str,
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AuditLogListResponse:
    """List audit logs for an organization."""
    service = _get_service(session)
    logs = await service.list_organization_logs(
        org_id,
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        offset=offset,
        limit=limit,
    )
    total = await service.count_organization_logs(org_id)
    return AuditLogListResponse(
        items=[_log_to_response(entry) for entry in logs],
        total=total,
        offset=offset,
        limit=limit,
    )


@audit_router.get("/me/{user_id}", response_model=AuditLogListResponse)
async def list_user_audit_logs(
    user_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AuditLogListResponse:
    """List audit logs for a specific user."""
    service = _get_service(session)
    logs = await service.list_user_logs(user_id, offset=offset, limit=limit)
    return AuditLogListResponse(
        items=[_log_to_response(entry) for entry in logs],
        total=len(logs),
        offset=offset,
        limit=limit,
    )
