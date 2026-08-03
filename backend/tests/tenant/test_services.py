"""Tests for tenant services."""

from unittest.mock import AsyncMock

import pytest

from app.kernel.exceptions.errors import ConflictError, UnauthorizedError
from app.tenant.domain.enums import OrganizationRole
from app.tenant.services.tenant_service import InvitationService, OrganizationService


@pytest.fixture
def mock_org_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.exists_by_slug.return_value = False
    repo.find_by_id.return_value = None
    repo.find_by_slug.return_value = None
    return repo


@pytest.fixture
def mock_membership_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_user_and_org.return_value = None
    repo.list_by_user.return_value = []
    return repo


@pytest.fixture
def mock_invitation_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_pending_by_email_and_org.return_value = None
    repo.find_by_id.return_value = None
    return repo


@pytest.fixture
def org_service(
    mock_org_repo: AsyncMock,
    mock_membership_repo: AsyncMock,
) -> OrganizationService:
    return OrganizationService(mock_org_repo, mock_membership_repo)


@pytest.fixture
def invitation_service(
    mock_invitation_repo: AsyncMock,
    mock_membership_repo: AsyncMock,
) -> InvitationService:
    return InvitationService(mock_invitation_repo, mock_membership_repo)


@pytest.mark.asyncio
async def test_create_organization(
    org_service: OrganizationService,
    mock_org_repo: AsyncMock,
    mock_membership_repo: AsyncMock,
) -> None:
    org = await org_service.create_organization(
        name="Acme",
        slug="acme",
        owner_id="user-1",
    )
    assert org.name == "Acme"
    mock_org_repo.save.assert_awaited_once()
    mock_membership_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_organization_duplicate_slug(
    org_service: OrganizationService,
    mock_org_repo: AsyncMock,
) -> None:
    mock_org_repo.exists_by_slug.return_value = True
    with pytest.raises(ConflictError):
        await org_service.create_organization(
            name="Acme",
            slug="acme",
            owner_id="user-1",
        )


@pytest.mark.asyncio
async def test_check_membership_not_found(
    org_service: OrganizationService,
) -> None:
    with pytest.raises(UnauthorizedError):
        await org_service.check_membership("user-1", "org-1")


@pytest.mark.asyncio
async def test_invite_member(
    invitation_service: InvitationService,
    mock_invitation_repo: AsyncMock,
) -> None:
    inv = await invitation_service.invite_member(
        email="new@example.com",
        organization_id="org-1",
        role=OrganizationRole.MEMBER,
        invited_by="user-1",
    )
    assert inv.email == "new@example.com"
    mock_invitation_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_invite_member_duplicate(
    invitation_service: InvitationService,
    mock_invitation_repo: AsyncMock,
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.tenant.domain.entities import Invitation

    existing = Invitation(
        email="dup@example.com",
        organization_id="org-1",
        invited_by="user-1",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_invitation_repo.find_pending_by_email_and_org.return_value = existing
    with pytest.raises(ConflictError):
        await invitation_service.invite_member(
            email="dup@example.com",
            organization_id="org-1",
            role=OrganizationRole.MEMBER,
            invited_by="user-1",
        )
