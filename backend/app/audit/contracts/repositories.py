"""Repository contracts for Audit Trail."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.audit.domain.entities import AuditLog


class AuditLogRepository(ABC):
    """Abstract repository for AuditLog entries (append-only)."""

    @abstractmethod
    async def save(self, entry: AuditLog) -> None:
        """Persist an audit log entry."""

    @abstractmethod
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
        """List audit logs for an organization with optional filters."""

    @abstractmethod
    async def list_by_user(
        self,
        user_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[AuditLog]:
        """List audit logs for a user."""

    @abstractmethod
    async def count_by_organization(
        self,
        organization_id: str,
    ) -> int:
        """Count audit logs for an organization."""
