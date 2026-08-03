"""Repository contracts for the Project domain."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.kernel.entities.base import UUIDv7
    from app.project.domain.entities import Project


class ProjectRepository(ABC):
    """Abstract repository for Project aggregates."""

    @abstractmethod
    async def save(self, project: Project) -> None:
        """Persist a project."""

    @abstractmethod
    async def find_by_id(self, project_id: UUIDv7) -> Project | None:
        """Find a project by ID."""

    @abstractmethod
    async def find_by_org_and_name(
        self,
        org_id: str,
        name: str,
    ) -> Project | None:
        """Find a project by organization and name."""

    @abstractmethod
    async def list_by_organization(
        self,
        org_id: str,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Project]:
        """List projects for an organization."""

    @abstractmethod
    async def count_by_organization(self, org_id: str) -> int:
        """Count projects in an organization."""

    @abstractmethod
    async def delete(self, project_id: UUIDv7) -> bool:
        """Delete a project."""
