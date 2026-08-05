"""Command and query handlers for evaluation run management."""

from __future__ import annotations

from app.evaluation.application.run_commands import (
    CancelEvaluationRunCommand,
    CompleteEvaluationRunCommand,
    CreateEvaluationRunCommand,
    FailEvaluationRunCommand,
    GetEvaluationRunQuery,
    ListEvaluationRunsQuery,
    QueueEvaluationRunCommand,
    RetryEvaluationRunCommand,
    StartEvaluationRunCommand,
    UpdateRunProgressCommand,
)
from app.evaluation.domain.contracts.evaluation_contracts import (
    PaginatedRuns,
    RunQuery,
    RunRepository,
)
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import (
    CancellationReason,
    EvaluationType,
    RunStatus,
)
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, ValidationError


class CreateEvaluationRunHandler:
    """Handler for creating evaluation runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: CreateEvaluationRunCommand) -> EvaluationRun:
        """Execute the create run command.

        Args:
            command: The create command.

        Returns:
            The created EvaluationRun aggregate.

        Raises:
            ValidationError: If required fields are missing.

        """
        if not command.provider:
            raise ValidationError(message="Provider is required", field="provider")
        if not command.model:
            raise ValidationError(message="Model is required", field="model")

        profile = EvaluationProfile(
            provider_name=command.provider,
            model_id=command.model,
            system_prompt=command.system_prompt,
        )

        config = EvaluationConfiguration(
            name=command.config_name or command.evaluation_name,
            eval_type=EvaluationType(command.eval_type),
            profile=profile,
            metrics=command.metrics or ("accuracy",),
            prompt_template=command.prompt_template,
        )

        metadata = EvaluationMetadata(
            project_id=command.project_id,
            created_by=command.created_by,
            tags=command.tags,
        )

        run = EvaluationRun(
            evaluation_name=command.evaluation_name,
            config=config,
            profile=profile,
            metadata=metadata,
            evaluation_id=command.evaluation_id,
            workflow_id=command.workflow_id,
        )

        await self._repository.save(run)
        return run


class QueueEvaluationRunHandler:
    """Handler for queuing evaluation runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: QueueEvaluationRunCommand) -> EvaluationRun:
        """Execute the queue run command.

        Args:
            command: The queue command.

        Returns:
            The queued EvaluationRun aggregate.

        Raises:
            NotFoundError: If run not found.
            ConflictError: If run cannot be queued.

        """
        run = await self._get_run(command.run_id)
        run.queue()
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> EvaluationRun:
        """Retrieve run or raise NotFoundError."""
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {run_id}",
                resource_type="EvaluationRun",
                resource_id=run_id,
            )
        return run


class StartEvaluationRunHandler:
    """Handler for starting queued runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: StartEvaluationRunCommand) -> EvaluationRun:
        """Execute the start run command.

        Args:
            command: The start command.

        Returns:
            The started EvaluationRun aggregate.

        Raises:
            NotFoundError: If run not found.
            ConflictError: If run cannot be started.

        """
        run = await self._get_run(command.run_id)
        run.start(total_items=command.total_items)
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> EvaluationRun:
        """Retrieve run or raise NotFoundError."""
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {run_id}",
                resource_type="EvaluationRun",
                resource_id=run_id,
            )
        return run


class UpdateRunProgressHandler:
    """Handler for updating run progress."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: UpdateRunProgressCommand) -> EvaluationRun:
        """Execute the update progress command.

        Args:
            command: The progress command.

        Returns:
            The updated EvaluationRun aggregate.

        Raises:
            NotFoundError: If run not found.

        """
        run = await self._get_run(command.run_id)

        for _ in range(command.items_completed - (run.items_completed - run.items_failed)):
            run.record_item_success()
        for _ in range(command.items_failed):
            run.record_item_failure()

        if command.token_input or command.token_output:
            run.record_token_usage(command.token_input, command.token_output)
        if command.cost_usd:
            run.record_cost(command.cost_usd)
        if command.latency_ms:
            run.record_latency(command.latency_ms)

        await self._repository.persist_progress(run)
        return run

    async def _get_run(self, run_id: str) -> EvaluationRun:
        """Retrieve run or raise NotFoundError."""
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {run_id}",
                resource_type="EvaluationRun",
                resource_id=run_id,
            )
        return run


class CompleteEvaluationRunHandler:
    """Handler for completing runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: CompleteEvaluationRunCommand) -> EvaluationRun:
        """Execute the complete run command.

        Args:
            command: The complete command.

        Returns:
            The completed EvaluationRun aggregate.

        Raises:
            NotFoundError: If run not found.
            ConflictError: If run cannot be completed.

        """
        run = await self._get_run(command.run_id)
        run.complete()
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> EvaluationRun:
        """Retrieve run or raise NotFoundError."""
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {run_id}",
                resource_type="EvaluationRun",
                resource_id=run_id,
            )
        return run


class FailEvaluationRunHandler:
    """Handler for failing runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: FailEvaluationRunCommand) -> EvaluationRun:
        """Execute the fail run command.

        Args:
            command: The fail command.

        Returns:
            The failed EvaluationRun aggregate.

        Raises:
            NotFoundError: If run not found.
            ConflictError: If run cannot be failed.

        """
        run = await self._get_run(command.run_id)
        run.fail(error_code=command.error_code, error_message=command.error_message)
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> EvaluationRun:
        """Retrieve run or raise NotFoundError."""
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {run_id}",
                resource_type="EvaluationRun",
                resource_id=run_id,
            )
        return run


class CancelEvaluationRunHandler:
    """Handler for cancelling runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: CancelEvaluationRunCommand) -> EvaluationRun:
        """Execute the cancel run command.

        Args:
            command: The cancel command.

        Returns:
            The cancelled EvaluationRun aggregate.

        Raises:
            NotFoundError: If run not found.
            ConflictError: If run cannot be cancelled.

        """
        run = await self._get_run(command.run_id)
        reason = CancellationReason(command.reason)
        run.cancel(reason=reason, force=command.force)
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> EvaluationRun:
        """Retrieve run or raise NotFoundError."""
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {run_id}",
                resource_type="EvaluationRun",
                resource_id=run_id,
            )
        return run


class RetryEvaluationRunHandler:
    """Handler for retrying failed runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, command: RetryEvaluationRunCommand) -> EvaluationRun:
        """Execute the retry run command.

        Creates a new run from the failed run's configuration.

        Args:
            command: The retry command.

        Returns:
            The new EvaluationRun aggregate.

        Raises:
            NotFoundError: If source run not found.

        """
        r_id = UUIDv7.from_string(command.run_id)
        source = await self._repository.find_by_id(r_id)
        if source is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {command.run_id}",
                resource_type="EvaluationRun",
                resource_id=command.run_id,
            )

        if source.status not in (RunStatus.FAILED, RunStatus.TIMEDOUT):
            raise ConflictError(
                message="Only failed or timed-out runs can be retried",
                details={"run_id": command.run_id, "status": source.status.value},
            )

        new_run = EvaluationRun(
            evaluation_name=source.evaluation_name,
            config=source.config,
            profile=source.profile,
            metadata=source.metadata,
            evaluation_id=source.evaluation_id,
        )

        await self._repository.save(new_run)
        return new_run


class GetEvaluationRunHandler:
    """Handler for getting a single run."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, query: GetEvaluationRunQuery) -> EvaluationRun:
        """Execute the get run query.

        Args:
            query: The get query.

        Returns:
            The EvaluationRun aggregate.

        Raises:
            NotFoundError: If run not found.

        """
        r_id = UUIDv7.from_string(query.run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Evaluation run not found: {query.run_id}",
                resource_type="EvaluationRun",
                resource_id=query.run_id,
            )
        return run


class ListEvaluationRunsHandler:
    """Handler for listing runs."""

    def __init__(self, repository: RunRepository) -> None:
        """Initialize with repository dependency."""
        self._repository = repository

    async def handle(self, query: ListEvaluationRunsQuery) -> PaginatedRuns:
        """Execute the list runs query.

        Args:
            query: The list query.

        Returns:
            Paginated list of evaluation runs.

        """
        status = None
        if query.status is not None:
            status = RunStatus(query.status)

        repo_query = RunQuery(
            evaluation_id=query.evaluation_id,
            status=status,
            provider=query.provider,
            model=query.model,
            search=query.search,
            sort_by=query.sort_by,
            sort_order=query.sort_order,
            page=query.page,
            page_size=query.page_size,
        )
        return await self._repository.list(repo_query)
