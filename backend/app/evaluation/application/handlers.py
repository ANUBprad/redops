"""Command and query handlers for evaluation management."""

from __future__ import annotations

from app.evaluation.application.commands import (
    ArchiveEvaluationCommand,
    CreateEvaluationCommand,
    DeleteEvaluationCommand,
    DuplicateEvaluationCommand,
    GetEvaluationQuery,
    ListEvaluationsQuery,
    MarkReadyEvaluationCommand,
    UpdateEvaluationCommand,
)
from app.evaluation.domain.contracts.evaluation_contracts import (
    EvaluationQuery,
    EvaluationRepository,
    PaginatedEvaluations,
)
from app.evaluation.domain.entities.evaluation_definition import Evaluation
from app.evaluation.domain.enums.evaluation_enums import EvaluationStatus
from app.evaluation.domain.value_objects.evaluation_definition_vos import (
    EvaluationDescription,
    EvaluationName,
    MetricId,
    ProviderId,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, ValidationError


class CreateEvaluationHandler:
    """Handler for creating evaluation definitions."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: CreateEvaluationCommand) -> Evaluation:
        """Execute the create evaluation command.

        Args:
            command: The create command.

        Returns:
            The created Evaluation aggregate.

        Raises:
            ValidationError: If required fields are missing.
            ConflictError: If name already exists in the project.

        """
        name = EvaluationName(value=command.name)
        provider = ProviderId(value=command.provider)
        metrics = tuple(MetricId(value=m) for m in command.metrics)

        if not command.provider:
            raise ValidationError(message="Provider is required", field="provider")
        if not command.model:
            raise ValidationError(message="Model is required", field="model")

        # Check name uniqueness within project
        exists = await self._repository.exists_by_name_in_project(
            project_id=command.project_id,
            name=str(name.value),
        )
        if exists:
            raise ConflictError(
                message=f"Evaluation with name '{name.value}' already exists in project",
                details={"project_id": command.project_id, "name": str(name.value)},
            )

        evaluation = Evaluation.create(
            project_id=command.project_id,
            dataset_id=command.dataset_id,
            name=name,
            description=EvaluationDescription(value=command.description)
            if command.description is not None
            else None,
            provider=provider,
            model=command.model,
            metrics=metrics,
            tags=command.tags,
            configuration=command.configuration,
            created_by=command.created_by,
        )

        await self._repository.create(evaluation)
        return evaluation


class UpdateEvaluationHandler:
    """Handler for updating evaluation definitions."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: UpdateEvaluationCommand) -> Evaluation:
        """Execute the update evaluation command.

        Args:
            command: The update command.

        Returns:
            The updated Evaluation aggregate.

        Raises:
            NotFoundError: If evaluation not found.
            ConflictError: If name conflicts with another in the project.

        """
        evaluation = await self._get_evaluation(command.evaluation_id)

        # Check name uniqueness if name is being changed
        if command.name is not None:
            new_name = EvaluationName(value=command.name)
            exists = await self._repository.exists_by_name_in_project(
                project_id=evaluation.project_id,
                name=str(new_name.value),
                exclude_id=evaluation.id,
            )
            if exists:
                raise ConflictError(
                    message=f"Evaluation with name '{new_name.value}' already exists",
                    details={"name": str(new_name.value)},
                )

        evaluation.update(
            name=EvaluationName(value=command.name) if command.name is not None else None,
            description=EvaluationDescription(value=command.description)
            if command.description is not None
            else None,
            provider=ProviderId(value=command.provider) if command.provider is not None else None,
            model=command.model,
            metrics=tuple(MetricId(value=m) for m in command.metrics)
            if command.metrics is not None
            else None,
            tags=command.tags,
            configuration=command.configuration,
            dataset_id=command.dataset_id,
        )

        await self._repository.update(evaluation)
        return evaluation

    async def _get_evaluation(self, evaluation_id: str) -> Evaluation:
        """Retrieve evaluation or raise NotFoundError."""
        ev_id = UUIDv7.from_string(evaluation_id)
        evaluation = await self._repository.get_by_id(ev_id)
        if evaluation is None:
            raise NotFoundError(
                message=f"Evaluation not found: {evaluation_id}",
                resource_type="Evaluation",
                resource_id=evaluation_id,
            )
        return evaluation


class DeleteEvaluationHandler:
    """Handler for deleting evaluation definitions."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: DeleteEvaluationCommand) -> None:
        """Execute the delete evaluation command.

        Args:
            command: The delete command.

        Raises:
            NotFoundError: If evaluation not found.

        """
        ev_id = UUIDv7.from_string(command.evaluation_id)
        evaluation = await self._repository.get_by_id(ev_id)
        if evaluation is None:
            raise NotFoundError(
                message=f"Evaluation not found: {command.evaluation_id}",
                resource_type="Evaluation",
                resource_id=command.evaluation_id,
            )
        evaluation.delete()
        await self._repository.delete(ev_id)


class DuplicateEvaluationHandler:
    """Handler for duplicating evaluation definitions."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: DuplicateEvaluationCommand) -> Evaluation:
        """Execute the duplicate evaluation command.

        Args:
            command: The duplicate command.

        Returns:
            The duplicated Evaluation aggregate.

        Raises:
            NotFoundError: If source evaluation not found.
            ConflictError: If name already exists in the project.

        """
        ev_id = UUIDv7.from_string(command.evaluation_id)
        source = await self._repository.get_by_id(ev_id)
        if source is None:
            raise NotFoundError(
                message=f"Evaluation not found: {command.evaluation_id}",
                resource_type="Evaluation",
                resource_id=command.evaluation_id,
            )

        new_name = EvaluationName(value=command.new_name)

        # Check name uniqueness
        exists = await self._repository.exists_by_name_in_project(
            project_id=source.project_id,
            name=str(new_name.value),
        )
        if exists:
            raise ConflictError(
                message=f"Evaluation with name '{new_name.value}' already exists",
                details={"name": str(new_name.value)},
            )

        duplicate = source.duplicate(new_name)
        await self._repository.create(duplicate)
        return duplicate


class ArchiveEvaluationHandler:
    """Handler for archiving evaluation definitions."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: ArchiveEvaluationCommand) -> Evaluation:
        """Execute the archive evaluation command.

        Args:
            command: The archive command.

        Returns:
            The archived Evaluation aggregate.

        Raises:
            NotFoundError: If evaluation not found.

        """
        ev_id = UUIDv7.from_string(command.evaluation_id)
        evaluation = await self._repository.get_by_id(ev_id)
        if evaluation is None:
            raise NotFoundError(
                message=f"Evaluation not found: {command.evaluation_id}",
                resource_type="Evaluation",
                resource_id=command.evaluation_id,
            )
        evaluation.archive()
        await self._repository.update(evaluation)
        return evaluation


class MarkReadyEvaluationHandler:
    """Handler for marking evaluations as ready."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: MarkReadyEvaluationCommand) -> Evaluation:
        """Execute the mark-ready evaluation command.

        Args:
            command: The mark-ready command.

        Returns:
            The ready Evaluation aggregate.

        Raises:
            NotFoundError: If evaluation not found.

        """
        ev_id = UUIDv7.from_string(command.evaluation_id)
        evaluation = await self._repository.get_by_id(ev_id)
        if evaluation is None:
            raise NotFoundError(
                message=f"Evaluation not found: {command.evaluation_id}",
                resource_type="Evaluation",
                resource_id=command.evaluation_id,
            )
        evaluation.mark_ready()
        await self._repository.update(evaluation)
        return evaluation


class GetEvaluationHandler:
    """Handler for getting a single evaluation."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, query: GetEvaluationQuery) -> Evaluation:
        """Execute the get evaluation query.

        Args:
            query: The get query.

        Returns:
            The Evaluation aggregate.

        Raises:
            NotFoundError: If evaluation not found.

        """
        ev_id = UUIDv7.from_string(query.evaluation_id)
        evaluation = await self._repository.get_by_id(ev_id)
        if evaluation is None:
            raise NotFoundError(
                message=f"Evaluation not found: {query.evaluation_id}",
                resource_type="Evaluation",
                resource_id=query.evaluation_id,
            )
        return evaluation


class ListEvaluationsHandler:
    """Handler for listing evaluations."""

    def __init__(self, repository: EvaluationRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, query: ListEvaluationsQuery) -> PaginatedEvaluations:
        """Execute the list evaluations query.

        Args:
            query: The list query.

        Returns:
            Paginated list of evaluations.

        """
        status = None
        if query.status is not None:
            status = EvaluationStatus(query.status)

        repo_query = EvaluationQuery(
            project_id=query.project_id,
            provider=query.provider,
            model=query.model,
            status=status,
            search=query.search,
            sort_by=query.sort_by,
            sort_order=query.sort_order,
            page=query.page,
            page_size=query.page_size,
        )
        return await self._repository.list(repo_query)
