"""Repository contracts for the Tenant domain."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.kernel.entities.base import UUIDv7
    from app.tenant.domain.entities import Invitation, Membership, Organization


class OrganizationRepository(ABC):
    """Abstract repository for Organization aggregates."""

    @abstractmethod
    async def save(self, org: Organization) -> None:
        """Persist an organization."""

    @abstractmethod
    async def find_by_id(self, org_id: UUIDv7) -> Organization | None:
        """Find an organization by ID."""

    @abstractmethod
    async def find_by_slug(self, slug: str) -> Organization | None:
        """Find an organization by slug."""

    @abstractmethod
    async def exists_by_slug(self, slug: str) -> bool:
        """Check if a slug is taken."""

    @abstractmethod
    async def list_by_owner(self, owner_id: str) -> list[Organization]:
        """List organizations owned by a user."""


class MembershipRepository(ABC):
    """Abstract repository for Membership entities."""

    @abstractmethod
    async def save(self, membership: Membership) -> None:
        """Persist a membership."""

    @abstractmethod
    async def find_by_user_and_org(
        self,
        user_id: str,
        org_id: str,
    ) -> Membership | None:
        """Find a membership by user and org."""

    @abstractmethod
    async def list_by_org(self, org_id: str) -> list[Membership]:
        """List all memberships in an organization."""

    @abstractmethod
    async def list_by_user(self, user_id: str) -> list[Membership]:
        """List all organizations a user belongs to."""

    @abstractmethod
    async def delete(self, user_id: str, org_id: str) -> bool:
        """Remove a membership."""


class InvitationRepository(ABC):
    """Abstract repository for Invitation entities."""

    @abstractmethod
    async def save(self, invitation: Invitation) -> None:
        """Persist an invitation."""

    @abstractmethod
    async def find_by_id(self, invitation_id: UUIDv7) -> Invitation | None:
        """Find an invitation by ID."""

    @abstractmethod
    async def find_pending_by_email_and_org(
        self,
        email: str,
        org_id: str,
    ) -> Invitation | None:
        """Find a pending invitation by email and org."""

    @abstractmethod
    async def list_by_org(self, org_id: str) -> list[Invitation]:
        """List all invitations for an organization."""

    @abstractmethod
    async def delete_expired(self) -> int:
        """Delete expired invitations. Returns count deleted."""
