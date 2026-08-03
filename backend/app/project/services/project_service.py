"""Project service."""

from __future__ import annotations

from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, UnauthorizedError
from app.project.contracts.repositories import ProjectRepository
from app.project.domain.entities import Project


class ProjectService:
    """Service for project operations with tenant isolation."""

    def __init__(self, repo: ProjectRepository) -> None:
        self._repo = repo

    async def create_project(
        self,
        *,
        name: str,
        organization_id: str,
        created_by: str | None = None,
        description: str | None = None,
    ) -> Project:
        existing = await self._repo.find_by_org_and_name(organization_id, name)
        if existing is not None:
            raise ConflictError(
                message="A project with this name already exists in this organization",
                details={"name": name, "organization_id": organization_id},
            )
        project = Project.create(
            name=name,
            organization_id=organization_id,
            created_by=created_by,
            description=description,
        )
        await self._repo.save(project)
        return project

    async def get_project(
        self,
        project_id: str,
        organization_id: str,
    ) -> Project:
        project = await self._repo.find_by_id(UUIDv7.from_string(project_id))
        if project is None:
            raise NotFoundError(
                message="Project not found",
                resource_type="Project",
                resource_id=project_id,
            )
        if project.organization_id != organization_id:
            raise UnauthorizedError(
                message="Project does not belong to this organization",
            )
        return project

    async def list_projects(
        self,
        organization_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Project]:
        return await self._repo.list_by_organization(
            organization_id,
            offset=offset,
            limit=limit,
        )

    async def update_project(
        self,
        project_id: str,
        organization_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        project = await self.get_project(project_id, organization_id)
        project.update(name=name, description=description)
        await self._repo.save(project)
        return project

    async def delete_project(
        self,
        project_id: str,
        organization_id: str,
    ) -> bool:
        project = await self.get_project(project_id, organization_id)
        project.deactivate()
        await self._repo.save(project)
        return True
