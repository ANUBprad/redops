"""Command and query handlers for agent run management."""

from __future__ import annotations

from app.agents.application.run_commands import (
    CancelAgentRunCommand,
    CompleteAgentRunCommand,
    CreateAgentRunCommand,
    FailAgentRunCommand,
    GetAgentRunQuery,
    ListAgentRunsQuery,
    QueueAgentRunCommand,
    RetryAgentRunCommand,
    StartAgentRunCommand,
    UpdateAgentRunProgressCommand,
)
from app.agents.domain.contracts.agent_contracts import (
    AgentRunQuery,
    AgentRunRepository,
    PaginatedAgentRuns,
)
from app.agents.domain.entities.agent_entities import AgentRun
from app.agents.domain.enums.agent_enums import (
    AgentCancellationReason,
    AgentRunStatus,
)
from app.agents.domain.value_objects.agent_value_objects import (
    AgentConfiguration,
    AgentProfile,
    AgentRunMetadata,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError, NotFoundError, ValidationError


class CreateAgentRunHandler:
    """Handler for creating agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: CreateAgentRunCommand) -> AgentRun:
        if not command.provider:
            raise ValidationError(message="Provider is required", field="provider")
        if not command.model:
            raise ValidationError(message="Model is required", field="model")

        profile = AgentProfile(
            provider_name=command.provider,
            model_id=command.model,
        )

        config = AgentConfiguration(
            name=command.agent_name,
            profile=profile,
            tools=command.tools,
            max_steps=command.max_steps,
            timeout_seconds=command.timeout_seconds,
        )

        metadata = AgentRunMetadata(
            project_id=command.project_id,
            created_by=command.created_by,
            tags=command.tags,
        )

        run = AgentRun(
            agent_name=command.agent_name,
            config=config,
            metadata=metadata,
            agent_definition_id=command.agent_definition_id,
            workflow_id=command.workflow_id,
        )

        await self._repository.save(run)
        return run


class QueueAgentRunHandler:
    """Handler for queuing agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: QueueAgentRunCommand) -> AgentRun:
        run = await self._get_run(command.run_id)
        run.queue()
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> AgentRun:
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Agent run not found: {run_id}",
                resource_type="AgentRun",
                resource_id=run_id,
            )
        return run


class StartAgentRunHandler:
    """Handler for starting queued agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: StartAgentRunCommand) -> AgentRun:
        run = await self._get_run(command.run_id)
        run.start(total_steps=command.total_steps)
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> AgentRun:
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Agent run not found: {run_id}",
                resource_type="AgentRun",
                resource_id=run_id,
            )
        return run


class UpdateAgentRunProgressHandler:
    """Handler for updating agent run progress."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: UpdateAgentRunProgressCommand) -> AgentRun:
        run = await self._get_run(command.run_id)

        for _ in range(command.steps_completed - (run.steps_completed - run.steps_failed)):
            run.record_step_success()
        for _ in range(command.steps_failed):
            run.record_step_failure()

        if command.token_input or command.token_output:
            run.record_token_usage(command.token_input, command.token_output)
        if command.cost_usd:
            run.record_cost(command.cost_usd)
        if command.latency_ms:
            run.record_latency(command.latency_ms)

        await self._repository.persist_progress(run)
        return run

    async def _get_run(self, run_id: str) -> AgentRun:
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Agent run not found: {run_id}",
                resource_type="AgentRun",
                resource_id=run_id,
            )
        return run


class CompleteAgentRunHandler:
    """Handler for completing agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: CompleteAgentRunCommand) -> AgentRun:
        run = await self._get_run(command.run_id)
        run.complete()
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> AgentRun:
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Agent run not found: {run_id}",
                resource_type="AgentRun",
                resource_id=run_id,
            )
        return run


class FailAgentRunHandler:
    """Handler for failing agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: FailAgentRunCommand) -> AgentRun:
        run = await self._get_run(command.run_id)
        run.fail(error_code=command.error_code, error_message=command.error_message)
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> AgentRun:
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Agent run not found: {run_id}",
                resource_type="AgentRun",
                resource_id=run_id,
            )
        return run


class CancelAgentRunHandler:
    """Handler for cancelling agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: CancelAgentRunCommand) -> AgentRun:
        run = await self._get_run(command.run_id)
        reason = AgentCancellationReason(command.reason)
        run.cancel(reason=reason, force=command.force)
        await self._repository.save(run)
        return run

    async def _get_run(self, run_id: str) -> AgentRun:
        r_id = UUIDv7.from_string(run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Agent run not found: {run_id}",
                resource_type="AgentRun",
                resource_id=run_id,
            )
        return run


class RetryAgentRunHandler:
    """Handler for retrying failed agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, command: RetryAgentRunCommand) -> AgentRun:
        r_id = UUIDv7.from_string(command.run_id)
        source = await self._repository.find_by_id(r_id)
        if source is None:
            raise NotFoundError(
                message=f"Agent run not found: {command.run_id}",
                resource_type="AgentRun",
                resource_id=command.run_id,
            )

        if source.status not in (AgentRunStatus.FAILED, AgentRunStatus.TIMEDOUT):
            raise ConflictError(
                message="Only failed or timed-out runs can be retried",
                details={"run_id": command.run_id, "status": source.status.value},
            )

        new_run = AgentRun(
            agent_name=source.agent_name,
            config=source.config,
            metadata=source.metadata,
            agent_definition_id=source.agent_definition_id,
        )

        await self._repository.save(new_run)
        return new_run


class GetAgentRunHandler:
    """Handler for getting a single agent run."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, query: GetAgentRunQuery) -> AgentRun:
        r_id = UUIDv7.from_string(query.run_id)
        run = await self._repository.find_by_id(r_id)
        if run is None:
            raise NotFoundError(
                message=f"Agent run not found: {query.run_id}",
                resource_type="AgentRun",
                resource_id=query.run_id,
            )
        return run


class ListAgentRunsHandler:
    """Handler for listing agent runs."""

    def __init__(self, repository: AgentRunRepository) -> None:
        self._repository = repository

    async def handle(self, query: ListAgentRunsQuery) -> PaginatedAgentRuns:
        status = None
        if query.status is not None:
            status = AgentRunStatus(query.status)

        repo_query = AgentRunQuery(
            agent_name=query.agent_name,
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
