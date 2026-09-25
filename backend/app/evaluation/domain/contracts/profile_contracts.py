"""Domain contracts for the Evaluation Profile aggregate."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.evaluation.domain.entities.profile import EvaluationProfileEntity
from app.kernel.entities.base import UUIDv7


@dataclass
class ProfileQuery:
    """Query parameters for listing profiles."""

    project_id: str | None = None
    search: str | None = None
    is_builtin: bool | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PaginatedProfiles:
    """Paginated result for profile listing."""

    items: list[EvaluationProfileEntity] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)


class ProfileRepository(ABC):
    """Repository for evaluation profile persistence."""

    @abstractmethod
    async def save(self, profile: EvaluationProfileEntity) -> None:
        """Save a profile (create or update)."""
        ...

    @abstractmethod
    async def find_by_id(self, profile_id: UUIDv7) -> EvaluationProfileEntity | None:
        """Find a profile by its ID."""
        ...

    @abstractmethod
    async def list(self, query: ProfileQuery) -> PaginatedProfiles:
        """List profiles with filtering, sorting, and pagination."""
        ...

    @abstractmethod
    async def delete(self, profile_id: UUIDv7) -> bool:
        """Delete a profile by ID."""
        ...

    @abstractmethod
    async def exists_by_name_in_project(
        self,
        project_id: str,
        name: str,
        exclude_id: UUIDv7 | None = None,
    ) -> bool:
        """Check whether a profile with the given name exists in a project."""
        ...
