"""SQLAlchemy repository implementation for Audit Logs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.audit.contracts.repositories import AuditLogRepository
from app.audit.domain.entities import AuditLog
from app.infrastructure.database.models.audit_log import AuditLogModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyAuditLogRepository(AuditLogRepository):
    """SQLAlchemy implementation of AuditLogRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, entry: AuditLog) -> None:
        model = AuditLogModel(
            log_id=entry.log_id,
            user_id=entry.user_id,
            user_email=entry.user_email,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            organization_id=entry.organization_id,
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
            metadata_=entry.metadata,
            timestamp=entry.timestamp,
            request_id=entry.request_id,
        )
        self._session.add(model)

    async def list_by_organization(
        self,
        organization_id: str,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        user_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = select(AuditLogModel).where(
            AuditLogModel.organization_id == organization_id,
        )
        if action is not None:
            stmt = stmt.where(AuditLogModel.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditLogModel.resource_type == resource_type)
        if user_id is not None:
            stmt = stmt.where(AuditLogModel.user_id == user_id)
        stmt = stmt.order_by(AuditLogModel.timestamp.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def list_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.user_id == user_id)
            .order_by(AuditLogModel.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_by_organization(self, organization_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(AuditLogModel)
            .where(
                AuditLogModel.organization_id == organization_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _to_domain(model: AuditLogModel) -> AuditLog:
        return AuditLog(
            log_id=model.log_id,
            user_id=model.user_id,
            user_email=model.user_email,
            action=model.action,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            organization_id=model.organization_id,
            ip_address=model.ip_address,
            user_agent=model.user_agent,
            metadata=model.metadata_,
            timestamp=model.timestamp,
            request_id=model.request_id,
        )
