"""SQLAlchemy repository implementations for Tenant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.infrastructure.database.models.tenant import (
    InvitationModel,
    MembershipModel,
    OrganizationModel,
)
from app.kernel.entities.base import UUIDv7
from app.tenant.contracts.repositories import (
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
)
from app.tenant.domain.entities import Invitation, Membership, Organization
from app.tenant.domain.enums import InvitationStatus, OrganizationRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyOrganizationRepository(OrganizationRepository):
    """SQLAlchemy implementation of OrganizationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, org: Organization) -> None:
        model = OrganizationModel(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            description=org.description,
            owner_id=org.owner_id,
            is_active=org.is_active,
            version=org.version,
            created_at=org.created_at,
            updated_at=org.updated_at,
        )
        self._session.add(model)

    async def find_by_id(self, org_id: UUIDv7) -> Organization | None:
        stmt = select(OrganizationModel).where(OrganizationModel.id == str(org_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_slug(self, slug: str) -> Organization | None:
        stmt = select(OrganizationModel).where(OrganizationModel.slug == slug.lower().strip())
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def exists_by_slug(self, slug: str) -> bool:
        stmt = select(OrganizationModel.id).where(OrganizationModel.slug == slug.lower().strip())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_by_owner(self, owner_id: str) -> list[Organization]:
        stmt = (
            select(OrganizationModel)
            .where(OrganizationModel.owner_id == owner_id)
            .order_by(OrganizationModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    @staticmethod
    def _to_domain(model: OrganizationModel) -> Organization:
        return Organization(
            entity_id=UUIDv7.from_string(model.id),
            name=model.name,
            slug=model.slug,
            description=model.description,
            owner_id=model.owner_id,
        )


class SqlAlchemyMembershipRepository(MembershipRepository):
    """SQLAlchemy implementation of MembershipRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, membership: Membership) -> None:
        model = MembershipModel(
            id=str(membership.id),
            user_id=membership.user_id,
            organization_id=membership.organization_id,
            role=membership.role.value,
            invited_by=membership.invited_by,
            is_active=membership.is_active,
            joined_at=membership.joined_at,
            created_at=membership.created_at,
        )
        self._session.add(model)

    async def find_by_user_and_org(
        self,
        user_id: str,
        org_id: str,
    ) -> Membership | None:
        stmt = select(MembershipModel).where(
            MembershipModel.user_id == user_id,
            MembershipModel.organization_id == org_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_org(self, org_id: str) -> list[Membership]:
        stmt = (
            select(MembershipModel)
            .where(MembershipModel.organization_id == org_id)
            .order_by(MembershipModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def list_by_user(self, user_id: str) -> list[Membership]:
        stmt = (
            select(MembershipModel)
            .where(MembershipModel.user_id == user_id)
            .order_by(MembershipModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def delete(self, user_id: str, org_id: str) -> bool:
        stmt = select(MembershipModel).where(
            MembershipModel.user_id == user_id,
            MembershipModel.organization_id == org_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    @staticmethod
    def _to_domain(model: MembershipModel) -> Membership:
        return Membership(
            entity_id=UUIDv7.from_string(model.id),
            user_id=model.user_id,
            organization_id=model.organization_id,
            role=OrganizationRole(model.role),
            invited_by=model.invited_by,
            joined_at=model.joined_at,
        )


class SqlAlchemyInvitationRepository(InvitationRepository):
    """SQLAlchemy implementation of InvitationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, invitation: Invitation) -> None:
        model = InvitationModel(
            id=str(invitation.id),
            email=invitation.email,
            organization_id=invitation.organization_id,
            role=invitation.role.value,
            invited_by=invitation.invited_by,
            status=invitation.status.value,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
        )
        self._session.add(model)

    async def find_by_id(self, invitation_id: UUIDv7) -> Invitation | None:
        stmt = select(InvitationModel).where(InvitationModel.id == str(invitation_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_pending_by_email_and_org(
        self,
        email: str,
        org_id: str,
    ) -> Invitation | None:
        stmt = select(InvitationModel).where(
            InvitationModel.email == email.lower().strip(),
            InvitationModel.organization_id == org_id,
            InvitationModel.status == InvitationStatus.PENDING.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_org(self, org_id: str) -> list[Invitation]:
        stmt = (
            select(InvitationModel)
            .where(InvitationModel.organization_id == org_id)
            .order_by(InvitationModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def delete_expired(self) -> int:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        stmt = select(InvitationModel).where(
            InvitationModel.expires_at < now,
            InvitationModel.status == InvitationStatus.PENDING.value,
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        for m in models:
            m.status = InvitationStatus.EXPIRED.value
        return len(models)

    @staticmethod
    def _to_domain(model: InvitationModel) -> Invitation:
        return Invitation(
            entity_id=UUIDv7.from_string(model.id),
            email=model.email,
            organization_id=model.organization_id,
            role=OrganizationRole(model.role),
            invited_by=model.invited_by,
            status=InvitationStatus(model.status),
            expires_at=model.expires_at,
        )
