"""Notification REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from app.notification.schemas.responses import (
    NotificationListResponse,
    NotificationResponse,
    SendNotificationRequest,
)
from app.notification.services.notification_service import NotificationService

notification_router = APIRouter(prefix="/notifications", tags=["notifications"])


def _get_service(session: AsyncSession) -> NotificationService:
    return NotificationService(SqlAlchemyNotificationRepository(session))


def _notification_to_response(n: object) -> NotificationResponse:
    from app.notification.domain.entities import Notification

    n2 = n if isinstance(n, Notification) else Notification()
    return NotificationResponse(
        notification_id=n2.notification_id,
        organization_id=n2.organization_id,
        user_id=n2.user_id,
        channel=n2.channel,
        event=n2.event,
        title=n2.title,
        message=n2.message,
        metadata=n2.metadata,
        status=n2.status,
        target=n2.target,
        error_message=n2.error_message,
        retry_count=n2.retry_count,
        timestamp=n2.timestamp.isoformat(),
    )


@notification_router.post("/send", response_model=NotificationResponse, status_code=201)
async def send_notification(
    body: SendNotificationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationResponse:
    """Send a notification."""
    service = _get_service(session)
    notification = await service.send_notification(
        organization_id=current_user.org_id or "",
        user_id=current_user.user_id,
        channel=body.channel,
        event=body.event,
        title=body.title,
        message=body.message,
        target=body.target,
        metadata=body.metadata,
    )
    return _notification_to_response(notification)


@notification_router.get("/{org_id}", response_model=NotificationListResponse)
async def list_notifications(
    org_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationListResponse:
    """List notifications for an organization."""
    service = _get_service(session)
    notifications = await service.list_organization_notifications(
        org_id,
        offset=offset,
        limit=limit,
    )
    total = await service.count_organization_notifications(org_id)
    return NotificationListResponse(
        items=[_notification_to_response(n) for n in notifications],
        total=total,
        offset=offset,
        limit=limit,
    )
