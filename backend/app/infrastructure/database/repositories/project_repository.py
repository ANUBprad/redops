"""SQLAlchemy repository implementation for Projects."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.infrastructure.database.models.project import ProjectModel
from app.kernel.entities.base import UUIDv7
from app.project.contracts.repositories import ProjectRepository
from app.project.domain.entities import Project

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyProjectRepository(ProjectRepository):
    """SQLAlchemy implementation of ProjectRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, project: Project) -> None:
        model = ProjectModel(
            id=str(project.id),
            name=project.name,
            description=project.description,
            organization_id=project.organization_id,
            created_by=project.created_by,
            is_active=project.is_active,
            version=project.version,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )
        self._session.add(model)

    async def find_by_id(self, project_id: UUIDv7) -> Project | None:
        stmt = select(ProjectModel).where(ProjectModel.id == str(project_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_org_and_name(
        self,
        org_id: str,
        name: str,
    ) -> Project | None:
        stmt = select(ProjectModel).where(
            ProjectModel.organization_id == org_id,
            ProjectModel.name == name.strip(),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def list_by_organization(
        self,
        org_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Project]:
        stmt = (
            select(ProjectModel)
            .where(
                ProjectModel.organization_id == org_id,
                ProjectModel.is_active.is_(True),
            )
            .order_by(ProjectModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_by_organization(self, org_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(ProjectModel)
            .where(
                ProjectModel.organization_id == org_id,
                ProjectModel.is_active.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete(self, project_id: UUIDv7) -> bool:
        stmt = select(ProjectModel).where(ProjectModel.id == str(project_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    @staticmethod
    def _to_domain(model: ProjectModel) -> Project:
        return Project(
            entity_id=UUIDv7.from_string(model.id),
            name=model.name,
            description=model.description,
            organization_id=model.organization_id,
            created_by=model.created_by,
        )
