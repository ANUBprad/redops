"""SQLAlchemy repository implementation for Notifications."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.infrastructure.database.models.notification import NotificationModel
from app.notification.contracts.repositories import NotificationRepository
from app.notification.domain.entities import Notification

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyNotificationRepository(NotificationRepository):
    """SQLAlchemy implementation of NotificationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, notification: Notification) -> None:
        model = NotificationModel(
            notification_id=notification.notification_id,
            organization_id=notification.organization_id,
            user_id=notification.user_id,
            channel=notification.channel,
            event=notification.event,
            title=notification.title,
            message=notification.message,
            metadata_=notification.metadata,
            status=notification.status,
            target=notification.target,
            error_message=notification.error_message,
            retry_count=notification.retry_count,
            timestamp=notification.timestamp,
        )
        self._session.add(model)

    async def find_by_id(self, notification_id: str) -> Notification | None:
        stmt = select(NotificationModel).where(
            NotificationModel.notification_id == notification_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Notification]:
        stmt = (
            select(NotificationModel)
            .where(NotificationModel.organization_id == organization_id)
            .order_by(NotificationModel.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def list_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Notification]:
        stmt = (
            select(NotificationModel)
            .where(NotificationModel.user_id == user_id)
            .order_by(NotificationModel.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_by_organization(self, organization_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(NotificationModel)
            .where(
                NotificationModel.organization_id == organization_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _to_domain(model: NotificationModel) -> Notification:
        return Notification(
            notification_id=model.notification_id,
            organization_id=model.organization_id,
            user_id=model.user_id,
            channel=model.channel,
            event=model.event,
            title=model.title,
            message=model.message,
            metadata=model.metadata_,
            status=model.status,
            target=model.target,
            error_message=model.error_message,
            retry_count=model.retry_count,
            timestamp=model.timestamp,
        )
