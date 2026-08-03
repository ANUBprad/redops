"""Tenant domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class OrganizationRole(StrEnum):
    """Role of a user within an organization."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class InvitationStatus(StrEnum):
    """Status of an organization invitation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"
