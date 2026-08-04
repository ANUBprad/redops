"""Tenant REST endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.repositories.tenant_repository import (
    SqlAlchemyInvitationRepository,
    SqlAlchemyMembershipRepository,
    SqlAlchemyOrganizationRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.tenant.domain.enums import OrganizationRole
from app.tenant.schemas.responses import (
    ChangeRoleRequest,
    CreateOrganizationRequest,
    InvitationResponse,
    InviteMemberRequest,
    MembershipResponse,
    OrganizationResponse,
    UpdateOrganizationRequest,
)
from app.tenant.services.tenant_service import InvitationService, OrganizationService

if TYPE_CHECKING:
    from app.tenant.domain.entities import Invitation, Membership, Organization

tenant_router = APIRouter(prefix="/organizations", tags=["organizations"])


def _get_org_service(session: AsyncSession) -> OrganizationService:
    return OrganizationService(
        SqlAlchemyOrganizationRepository(session),
        SqlAlchemyMembershipRepository(session),
    )


def _get_invitation_service(session: AsyncSession) -> InvitationService:
    return InvitationService(
        SqlAlchemyInvitationRepository(session),
        SqlAlchemyMembershipRepository(session),
    )


def _org_to_response(org: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=str(org.id),
        name=org.name,
        slug=org.slug,
        description=org.description,
        owner_id=org.owner_id,
        is_active=org.is_active,
        version=org.version,
        created_at=org.created_at.isoformat(),
        updated_at=org.updated_at.isoformat(),
    )


def _membership_to_response(m: Membership) -> MembershipResponse:
    return MembershipResponse(
        id=str(m.id),
        user_id=m.user_id,
        organization_id=m.organization_id,
        role=m.role.value,
        invited_by=m.invited_by,
        is_active=m.is_active,
        joined_at=m.joined_at.isoformat(),
        created_at=m.created_at.isoformat(),
    )


def _invitation_to_response(inv: Invitation) -> InvitationResponse:
    return InvitationResponse(
        id=str(inv.id),
        email=inv.email,
        organization_id=inv.organization_id,
        role=inv.role.value,
        invited_by=inv.invited_by,
        status=inv.status.value,
        expires_at=inv.expires_at.isoformat(),
        created_at=inv.created_at.isoformat(),
    )


@tenant_router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    body: CreateOrganizationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Create a new organization."""
    service = _get_org_service(session)
    try:
        org = await service.create_organization(
            name=body.name,
            slug=body.slug,
            owner_id=current_user.user_id,
            description=body.description,
        )
        return _org_to_response(org)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@tenant_router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrganizationResponse]:
    """List organizations the current user belongs to."""
    service = _get_org_service(session)
    orgs = await service.list_user_organizations(current_user.user_id)
    return [_org_to_response(o) for o in orgs]


@tenant_router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Get an organization by ID."""
    service = _get_org_service(session)
    try:
        await service.check_membership(current_user.user_id, org_id)
        org = await service.get_organization(org_id)
        return _org_to_response(org)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@tenant_router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    body: UpdateOrganizationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Update an organization."""
    service = _get_org_service(session)
    try:
        membership = await service.check_membership(current_user.user_id, org_id)
        if membership.role not in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
            raise BaseError(
                message="Insufficient permissions",
                http_status=403,
            )
        org = await service.update_organization(
            org_id,
            name=body.name,
            description=body.description,
        )
        return _org_to_response(org)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@tenant_router.get("/{org_id}/members", response_model=list[MembershipResponse])
async def list_members(
    org_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[MembershipResponse]:
    """List members of an organization."""
    service = _get_invitation_service(session)
    try:
        org_svc = _get_org_service(session)
        await org_svc.check_membership(current_user.user_id, org_id)
        members = await service.list_members(org_id)
        return [_membership_to_response(m) for m in members]
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@tenant_router.post("/{org_id}/members", response_model=InvitationResponse, status_code=201)
async def invite_member(
    org_id: str,
    body: InviteMemberRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> InvitationResponse:
    """Invite a member to an organization."""
    service = _get_invitation_service(session)
    try:
        org_svc = _get_org_service(session)
        await org_svc.check_membership(current_user.user_id, org_id)
        role = OrganizationRole(body.role)
        invitation = await service.invite_member(
            email=body.email,
            organization_id=org_id,
            role=role,
            invited_by=current_user.user_id,
        )
        return _invitation_to_response(invitation)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@tenant_router.post("/{org_id}/members/{user_id}/role", response_model=MembershipResponse)
async def change_member_role(
    org_id: str,
    user_id: str,
    body: ChangeRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MembershipResponse:
    """Change a member's role."""
    service = _get_invitation_service(session)
    try:
        org_svc = _get_org_service(session)
        await org_svc.check_membership(current_user.user_id, org_id)
        role = OrganizationRole(body.role)
        membership = await service.change_member_role(user_id, org_id, role)
        return _membership_to_response(membership)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@tenant_router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a member from an organization."""
    service = _get_invitation_service(session)
    try:
        org_svc = _get_org_service(session)
        await org_svc.check_membership(current_user.user_id, org_id)
        await service.remove_member(user_id, org_id)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@tenant_router.get("/{org_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    org_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[InvitationResponse]:
    """List pending invitations for an organization."""
    service = _get_invitation_service(session)
    try:
        org_svc = _get_org_service(session)
        await org_svc.check_membership(current_user.user_id, org_id)
        invitations = await service.list_invitations(org_id)
        return [_invitation_to_response(i) for i in invitations]
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
