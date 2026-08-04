"""Project REST endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.project.schemas.responses import (
    CreateProjectRequest,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.project.services.project_service import ProjectService

if TYPE_CHECKING:
    from app.project.domain.entities import Project

projects_router = APIRouter(
    prefix="/orgs/{org_id}/projects",
    tags=["projects"],
)


def _get_service(session: AsyncSession) -> ProjectService:
    return ProjectService(SqlAlchemyProjectRepository(session))


def _project_to_response(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        organization_id=p.organization_id,
        created_by=p.created_by,
        is_active=p.is_active,
        version=p.version,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@projects_router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    org_id: str,
    body: CreateProjectRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Create a new project within an organization."""
    service = _get_service(session)
    try:
        project = await service.create_project(
            name=body.name,
            organization_id=org_id,
            created_by=current_user.user_id,
            description=body.description,
        )
        return _project_to_response(project)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@projects_router.get("", response_model=list[ProjectResponse])
async def list_projects(
    org_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectResponse]:
    """List projects in an organization."""
    service = _get_service(session)
    projects = await service.list_projects(org_id)
    return [_project_to_response(p) for p in projects]


@projects_router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    org_id: str,
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Get a project by ID."""
    service = _get_service(session)
    try:
        project = await service.get_project(project_id, org_id)
        return _project_to_response(project)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@projects_router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    org_id: str,
    project_id: str,
    body: UpdateProjectRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Update a project."""
    service = _get_service(session)
    try:
        project = await service.update_project(
            project_id,
            org_id,
            name=body.name,
            description=body.description,
        )
        return _project_to_response(project)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@projects_router.delete("/{project_id}", status_code=204)
async def delete_project(
    org_id: str,
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a project (soft delete)."""
    service = _get_service(session)
    try:
        await service.delete_project(project_id, org_id)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
