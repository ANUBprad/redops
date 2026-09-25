"""Application service for Experiment management."""

from __future__ import annotations

from app.evaluation.domain.contracts.experiment_contracts import (
    ExperimentQuery,
    ExperimentRepository,
    PaginatedExperiments,
)
from app.evaluation.domain.entities.experiment import Experiment
from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.evaluation.domain.value_objects.experiment_value_objects import (
    ExperimentDescription,
    ExperimentName,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError


class ExperimentService:
    """Service for experiment CRUD and lifecycle operations."""

    def __init__(self, repo: ExperimentRepository) -> None:
        """Initialize with an experiment repository."""
        self._repo = repo

    async def create_experiment(
        self,
        *,
        project_id: str,
        name: str,
        description: str | None = None,
        hypothesis: str | None = None,
        tags: tuple[str, ...] = (),
        created_by: str | None = None,
    ) -> Experiment:
        """Create a new experiment.

        Raises:
            ValidationError: If a name already exists in the project.
            ConflictError: If name is duplicate within the project.

        """
        if await self._repo.exists_by_name_in_project(project_id, name):
            raise ConflictError(
                message=f"Experiment '{name}' already exists in this project",
                details={"project_id": project_id, "name": name},
            )
        experiment = Experiment.create(
            project_id=project_id,
            name=ExperimentName(value=name),
            description=ExperimentDescription(value=description) if description else None,
            hypothesis=hypothesis,
            tags=tags,
            created_by=created_by,
        )
        await self._repo.save(experiment)
        return experiment

    async def get_experiment(self, experiment_id: UUIDv7) -> Experiment:
        """Get an experiment by ID.

        Raises:
            NotFoundError: If the experiment does not exist.

        """
        experiment = await self._repo.find_by_id(experiment_id)
        if experiment is None:
            raise NotFoundError(
                message="Experiment not found",
                details={"experiment_id": str(experiment_id)},
            )
        return experiment

    async def list_experiments(self, query: ExperimentQuery) -> PaginatedExperiments:
        """List experiments with filtering and pagination."""
        return await self._repo.list(query)

    async def update_experiment(
        self,
        experiment_id: UUIDv7,
        *,
        name: str | None = None,
        description: str | None = None,
        hypothesis: str | None = None,
        conclusion: str | None = None,
        tags: tuple[str, ...] | None = None,
    ) -> Experiment:
        """Update experiment metadata.

        Raises:
            NotFoundError: If the experiment does not exist.
            ConflictError: If the experiment is completed or archived.

        """
        experiment = await self.get_experiment(experiment_id)
        experiment.update(
            name=ExperimentName(value=name) if name else None,
            description=ExperimentDescription(value=description) if description else None,
            hypothesis=hypothesis,
            conclusion=conclusion,
            tags=tags,
        )
        await self._repo.save(experiment)
        return experiment

    async def activate_experiment(self, experiment_id: UUIDv7) -> Experiment:
        """Activate a draft experiment."""
        experiment = await self.get_experiment(experiment_id)
        experiment.activate()
        await self._repo.save(experiment)
        return experiment

    async def complete_experiment(self, experiment_id: UUIDv7) -> Experiment:
        """Complete an active experiment."""
        experiment = await self.get_experiment(experiment_id)
        experiment.complete()
        await self._repo.save(experiment)
        return experiment

    async def archive_experiment(self, experiment_id: UUIDv7) -> Experiment:
        """Archive an experiment."""
        experiment = await self.get_experiment(experiment_id)
        experiment.archive()
        await self._repo.save(experiment)
        return experiment

    async def set_baseline(self, experiment_id: UUIDv7, run_id: str) -> Experiment:
        """Set the baseline run for comparison."""
        experiment = await self.get_experiment(experiment_id)
        experiment.set_baseline(run_id)
        await self._repo.save(experiment)
        return experiment

    async def delete_experiment(self, experiment_id: UUIDv7) -> bool:
        """Delete an experiment.

        Raises:
            NotFoundError: If the experiment does not exist.

        """
        experiment = await self.get_experiment(experiment_id)
        if experiment.status not in (ExperimentStatus.DRAFT, ExperimentStatus.ACTIVE):
            raise ConflictError(
                message="Only draft or active experiments can be deleted",
                details={"experiment_id": str(experiment_id), "status": experiment.status.value},
            )
        return await self._repo.delete(experiment_id)
