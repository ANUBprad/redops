"""Domain contracts for the Experiment aggregate."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.evaluation.domain.entities.experiment import Experiment
from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.kernel.entities.base import UUIDv7


@dataclass
class ExperimentQuery:
    """Query parameters for listing experiments."""

    project_id: str | None = None
    status: ExperimentStatus | None = None
    search: str | None = None
    tags: list[str] | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PaginatedExperiments:
    """Paginated result for experiment listing."""

    items: list[Experiment] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)


class ExperimentRepository(ABC):
    """Repository for experiment persistence."""

    @abstractmethod
    async def save(self, experiment: Experiment) -> None:
        """Save an experiment (create or update)."""
        ...

    @abstractmethod
    async def find_by_id(self, experiment_id: UUIDv7) -> Experiment | None:
        """Find an experiment by its ID."""
        ...

    @abstractmethod
    async def list(self, query: ExperimentQuery) -> PaginatedExperiments:
        """List experiments with filtering, sorting, and pagination."""
        ...

    @abstractmethod
    async def delete(self, experiment_id: UUIDv7) -> bool:
        """Delete an experiment by ID."""
        ...

    @abstractmethod
    async def exists_by_name_in_project(
        self,
        project_id: str,
        name: str,
        exclude_id: UUIDv7 | None = None,
    ) -> bool:
        """Check whether an experiment with the given name exists in a project."""
        ...
