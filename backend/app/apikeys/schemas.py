"""Pydantic schemas for API Keys."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateApiKeyRequest(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=list)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyResponse(BaseModel):
    """Response for an API key (without the raw key after creation)."""

    id: str
    name: str
    prefix: str
    user_id: str
    organization_id: str | None = None
    scopes: list[str]
    expires_at: str | None = None
    last_used_at: str | None = None
    usage_count: int = 0
    is_active: bool = True
    rotated_from: str | None = None
    created_at: str
    updated_at: str


class ApiKeyCreatedResponse(BaseModel):
    """Response when an API key is created (includes the raw key once)."""

    id: str
    name: str
    key: str
    prefix: str
    scopes: list[str]
    expires_at: str | None = None
    created_at: str
