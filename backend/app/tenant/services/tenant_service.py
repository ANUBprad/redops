"""Tenant services."""

from __future__ import annotations

from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, UnauthorizedError
from app.tenant.contracts.repositories import (
    InvitationRepository,
    MembershipRepository,
    OrganizationRepository,
)
from app.tenant.domain.entities import Invitation, Membership, Organization
from app.tenant.domain.enums import OrganizationRole


class OrganizationService:
    """Service for organization operations."""

    def __init__(
        self,
        org_repo: OrganizationRepository,
        membership_repo: MembershipRepository,
    ) -> None:
        self._org_repo = org_repo
        self._membership_repo = membership_repo

    async def create_organization(
        self,
        *,
        name: str,
        slug: str,
        owner_id: str,
        description: str | None = None,
    ) -> Organization:
        if await self._org_repo.exists_by_slug(slug):
            raise ConflictError(
                message="Organization slug already taken",
                details={"slug": slug},
            )
        org = Organization.create(
            name=name,
            slug=slug,
            owner_id=owner_id,
            description=description,
        )
        await self._org_repo.save(org)
        # Create owner membership
        owner_membership = Membership(
            user_id=owner_id,
            organization_id=str(org.id),
            role=OrganizationRole.OWNER,
            invited_by=owner_id,
        )
        await self._membership_repo.save(owner_membership)
        return org

    async def get_organization(self, org_id: str) -> Organization:
        org = await self._org_repo.find_by_id(UUIDv7.from_string(org_id))
        if org is None:
            raise NotFoundError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=org_id,
            )
        return org

    async def get_organization_by_slug(self, slug: str) -> Organization:
        org = await self._org_repo.find_by_slug(slug)
        if org is None:
            raise NotFoundError(
                message="Organization not found",
                resource_type="Organization",
                resource_id=slug,
            )
        return org

    async def list_user_organizations(self, user_id: str) -> list[Organization]:
        memberships = await self._membership_repo.list_by_user(user_id)
        orgs: list[Organization] = []
        for m in memberships:
            org = await self._org_repo.find_by_id(UUIDv7.from_string(m.organization_id))
            if org is not None and org.is_active:
                orgs.append(org)
        return orgs

    async def update_organization(
        self,
        org_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Organization:
        org = await self.get_organization(org_id)
        org.update(name=name, description=description)
        await self._org_repo.save(org)
        return org

    async def check_membership(
        self,
        user_id: str,
        org_id: str,
    ) -> Membership:
        membership = await self._membership_repo.find_by_user_and_org(user_id, org_id)
        if membership is None or not membership.is_active:
            raise UnauthorizedError(
                message="You are not a member of this organization",
                details={"user_id": user_id, "organization_id": org_id},
            )
        return membership


class InvitationService:
    """Service for invitation operations."""

    def __init__(
        self,
        invitation_repo: InvitationRepository,
        membership_repo: MembershipRepository,
    ) -> None:
        self._invitation_repo = invitation_repo
        self._membership_repo = membership_repo

    async def invite_member(
        self,
        *,
        email: str,
        organization_id: str,
        role: OrganizationRole,
        invited_by: str,
    ) -> Invitation:
        existing = await self._invitation_repo.find_pending_by_email_and_org(
            email,
            organization_id,
        )
        if existing is not None and existing.is_valid:
            raise ConflictError(
                message="A pending invitation already exists for this email",
                details={"email": email, "organization_id": organization_id},
            )
        invitation = Invitation(
            email=email,
            organization_id=organization_id,
            role=role,
            invited_by=invited_by,
        )
        await self._invitation_repo.save(invitation)
        return invitation

    async def accept_invitation(
        self,
        invitation_id: str,
    ) -> Invitation:
        invitation = await self._invitation_repo.find_by_id(
            UUIDv7.from_string(invitation_id),
        )
        if invitation is None:
            raise NotFoundError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=invitation_id,
            )
        invitation.accept()
        await self._invitation_repo.save(invitation)
        # Create membership
        membership = Membership(
            user_id=invitation.email,  # Will be resolved to user_id by caller
            organization_id=invitation.organization_id,
            role=invitation.role,
            invited_by=invitation.invited_by,
        )
        await self._membership_repo.save(membership)
        return invitation

    async def revoke_invitation(
        self,
        invitation_id: str,
    ) -> Invitation:
        invitation = await self._invitation_repo.find_by_id(
            UUIDv7.from_string(invitation_id),
        )
        if invitation is None:
            raise NotFoundError(
                message="Invitation not found",
                resource_type="Invitation",
                resource_id=invitation_id,
            )
        invitation.revoke()
        await self._invitation_repo.save(invitation)
        return invitation

    async def list_invitations(self, org_id: str) -> list[Invitation]:
        return await self._invitation_repo.list_by_org(org_id)

    async def list_members(self, org_id: str) -> list[Membership]:
        return await self._membership_repo.list_by_org(org_id)

    async def remove_member(
        self,
        user_id: str,
        org_id: str,
    ) -> bool:
        return await self._membership_repo.delete(user_id, org_id)

    async def change_member_role(
        self,
        user_id: str,
        org_id: str,
        new_role: OrganizationRole,
    ) -> Membership:
        membership = await self._membership_repo.find_by_user_and_org(user_id, org_id)
        if membership is None:
            raise NotFoundError(
                message="Membership not found",
                resource_type="Membership",
                resource_id=f"{user_id}:{org_id}",
            )
        membership.change_role(new_role)
        await self._membership_repo.save(membership)
        return membership
