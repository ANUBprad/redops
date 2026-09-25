"""REST endpoints for Evaluation Profile management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
)
from app.evaluation.domain.contracts.profile_contracts import ProfileQuery
from app.evaluation.services.profile_service import ProfileService
from app.infrastructure.database.repositories.profile_repository import (
    SqlAlchemyProfileRepository,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import BaseError

profile_router = APIRouter(prefix="/profiles", tags=["profiles"])


def _get_service(session: AsyncSession) -> ProfileService:
    """Create a service from the database session."""
    return ProfileService(SqlAlchemyProfileRepository(session))


# --- Schemas ---


class CreateProfileRequest(BaseModel):
    """Request body for creating a profile."""

    name: str = Field(..., min_length=1, max_length=255, description="Profile name")
    description: str | None = Field(default=None, description="Description")
    configuration: dict[str, Any] = Field(default_factory=dict, description="Profile configuration")


class UpdateProfileRequest(BaseModel):
    """Request body for updating a profile."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    configuration: dict[str, Any] | None = None


class ProfileResponse(BaseModel):
    """Response model for a profile."""

    id: str
    project_id: str
    name: str
    description: str | None = None
    scope: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    is_builtin: bool
    version: int
    created_at: str
    updated_at: str


class ProfileListResponse(BaseModel):
    """Paginated list response for profiles."""

    items: list[ProfileResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


def _to_response(profile: Any) -> ProfileResponse:
    """Convert domain profile to API response."""
    return ProfileResponse(
        id=str(profile.id),
        project_id=profile.project_id,
        name=str(profile.name.value),
        description=profile.description.value if profile.description else None,
        scope=profile.scope.value,
        configuration=profile.configuration,
        is_builtin=profile.is_builtin,
        version=profile.version,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )


# --- Endpoints ---


@profile_router.post("", response_model=ProfileResponse, status_code=201)
async def create_profile(
    body: CreateProfileRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileResponse:
    """Create a new evaluation profile."""
    service = _get_service(session)
    try:
        profile = await service.create_profile(
            project_id=str(current_user.org_id) if current_user.org_id else "",
            name=body.name,
            description=body.description,
            configuration=body.configuration,
        )
        await session.commit()
        return _to_response(profile)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@profile_router.get("", response_model=ProfileListResponse)
async def list_profiles(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    search: str | None = Query(default=None, description="Search by name"),
    is_builtin: bool | None = Query(default=None, description="Filter by builtin"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProfileListResponse:
    """List evaluation profiles with filtering and pagination."""
    service = _get_service(session)
    query = ProfileQuery(
        project_id=str(current_user.org_id) if current_user.org_id else None,
        search=search,
        is_builtin=is_builtin,
        page=page,
        page_size=page_size,
    )
    result = await service.list_profiles(query)
    return ProfileListResponse(
        items=[_to_response(p) for p in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@profile_router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileResponse:
    """Get a profile by ID."""
    service = _get_service(session)
    try:
        profile = await service.get_profile(UUIDv7.from_string(profile_id))
        return _to_response(profile)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@profile_router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    body: UpdateProfileRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProfileResponse:
    """Update a profile."""
    service = _get_service(session)
    try:
        profile = await service.update_profile(
            UUIDv7.from_string(profile_id),
            name=body.name,
            description=body.description,
            configuration=body.configuration,
        )
        await session.commit()
        return _to_response(profile)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@profile_router.delete("/{profile_id}", status_code=204)
async def delete_profile(
    profile_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a profile."""
    service = _get_service(session)
    try:
        await service.delete_profile(UUIDv7.from_string(profile_id))
        await session.commit()
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@profile_router.get("/{profile_id}/preview")
async def preview_profile(
    profile_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Preview the resolved configuration for a profile."""
    service = _get_service(session)
    try:
        config = await service.resolve_configuration(UUIDv7.from_string(profile_id))
        return config
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
