"""Tests for Tenant domain entities."""

from datetime import UTC, datetime, timedelta

from app.tenant.domain.entities import Invitation, Membership, Organization
from app.tenant.domain.enums import InvitationStatus, OrganizationRole


def test_organization_create() -> None:
    org = Organization.create(
        name="Test Org",
        slug="test-org",
        owner_id="user-1",
        description="A test org",
    )
    assert org.name == "Test Org"
    assert org.slug == "test-org"
    assert org.owner_id == "user-1"
    assert org.is_active is True


def test_organization_update() -> None:
    org = Organization.create(
        name="Test Org",
        slug="test-org",
        owner_id="user-1",
    )
    org.update(name="Updated Org", description="New description")
    assert org.name == "Updated Org"
    assert org.description == "New description"


def test_organization_deactivate_activate() -> None:
    org = Organization.create(
        name="Test Org",
        slug="test-org",
        owner_id="user-1",
    )
    org.deactivate()
    assert org.is_active is False
    org.activate()
    assert org.is_active is True


def test_membership() -> None:
    membership = Membership(
        user_id="user-1",
        organization_id="org-1",
        role=OrganizationRole.ADMIN,
    )
    assert membership.user_id == "user-1"
    assert membership.role == OrganizationRole.ADMIN
    assert membership.is_active is True


def test_membership_change_role() -> None:
    membership = Membership(
        user_id="user-1",
        organization_id="org-1",
        role=OrganizationRole.MEMBER,
    )
    membership.change_role(OrganizationRole.ADMIN)
    assert membership.role == OrganizationRole.ADMIN


def test_membership_deactivate() -> None:
    membership = Membership(
        user_id="user-1",
        organization_id="org-1",
        role=OrganizationRole.MEMBER,
    )
    membership.deactivate()
    assert membership.is_active is False


def test_invitation_create() -> None:
    inv = Invitation(
        email="invite@example.com",
        organization_id="org-1",
        role=OrganizationRole.MEMBER,
        invited_by="user-1",
    )
    assert inv.email == "invite@example.com"
    assert inv.role == OrganizationRole.MEMBER
    assert inv.status == InvitationStatus.PENDING
    assert inv.is_valid is True


def test_invitation_accept() -> None:
    inv = Invitation(
        email="invite@example.com",
        organization_id="org-1",
        role=OrganizationRole.MEMBER,
        invited_by="user-1",
    )
    inv.accept()
    assert inv.status == InvitationStatus.ACCEPTED


def test_invitation_revoke() -> None:
    inv = Invitation(
        email="invite@example.com",
        organization_id="org-1",
        role=OrganizationRole.MEMBER,
        invited_by="user-1",
    )
    inv.revoke()
    assert inv.status == InvitationStatus.REVOKED


def test_invitation_expiry() -> None:
    inv = Invitation(
        email="invite@example.com",
        organization_id="org-1",
        role=OrganizationRole.MEMBER,
        invited_by="user-1",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert inv.is_expired is True
    assert inv.is_valid is False
