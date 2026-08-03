"""Pydantic schemas for Tenant API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateOrganizationRequest(BaseModel):
    """Request body for creating an organization."""

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=2000)


class UpdateOrganizationRequest(BaseModel):
    """Request body for updating an organization."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class InviteMemberRequest(BaseModel):
    """Request body for inviting a member."""

    email: str
    role: str = Field(default="member")


class ChangeRoleRequest(BaseModel):
    """Request body for changing a member's role."""

    role: str


class OrganizationResponse(BaseModel):
    """Response for an organization."""

    id: str
    name: str
    slug: str
    description: str | None = None
    owner_id: str
    is_active: bool = True
    version: int = 1
    created_at: str
    updated_at: str


class MembershipResponse(BaseModel):
    """Response for a membership."""

    id: str
    user_id: str
    organization_id: str
    role: str
    invited_by: str | None = None
    is_active: bool = True
    joined_at: str
    created_at: str


class InvitationResponse(BaseModel):
    """Response for an invitation."""

    id: str
    email: str
    organization_id: str
    role: str
    invited_by: str
    status: str
    expires_at: str
    created_at: str
