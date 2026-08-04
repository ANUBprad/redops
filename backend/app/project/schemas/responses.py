"""Pydantic schemas for Project API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    """Request body for creating a project."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class UpdateProjectRequest(BaseModel):
    """Request body for updating a project."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ProjectResponse(BaseModel):
    """Response for a project."""

    id: str
    name: str
    description: str | None = None
    organization_id: str
    created_by: str | None = None
    is_active: bool = True
    version: int = 1
    created_at: str
    updated_at: str
