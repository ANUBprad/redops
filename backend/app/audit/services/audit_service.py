"""Audit service."""

from __future__ import annotations

from app.audit.contracts.repositories import AuditLogRepository
from app.audit.domain.entities import AuditLog


class AuditService:
    """Service for recording and querying audit logs."""

    def __init__(self, repo: AuditLogRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        user_id: str,
        user_email: str = "",
        action: str,
        resource_type: str,
        resource_id: str = "",
        organization_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, object] | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        """Record an audit log entry."""
        entry = AuditLog.create(
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            organization_id=organization_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata,
            request_id=request_id,
        )
        await self._repo.save(entry)
        return entry

    async def list_organization_logs(
        self,
        organization_id: str,
        *,
        action: str | None = None,
        resource_type: str | None = None,
        user_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit logs for an organization."""
        return await self._repo.list_by_organization(
            organization_id,
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            offset=offset,
            limit=limit,
        )

    async def list_user_logs(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit logs for a user."""
        return await self._repo.list_by_user(user_id, offset=offset, limit=limit)

    async def count_organization_logs(
        self,
        organization_id: str,
    ) -> int:
        """Count audit logs for an organization."""
        return await self._repo.count_by_organization(organization_id)
