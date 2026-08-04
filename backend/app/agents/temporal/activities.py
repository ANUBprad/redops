"""Temporal activities for agent run execution.

Activities call the existing application handlers, ensuring no
duplicate business logic. Each activity creates its own database
session via the configured session factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from temporalio import activity

from app.agents.application.run_commands import (
    CancelAgentRunCommand,
    CompleteAgentRunCommand,
    CreateAgentRunCommand,
    FailAgentRunCommand,
    QueueAgentRunCommand,
    StartAgentRunCommand,
    UpdateAgentRunProgressCommand,
)
from app.agents.application.run_handlers import (
    CancelAgentRunHandler,
    CompleteAgentRunHandler,
    CreateAgentRunHandler,
    FailAgentRunHandler,
    QueueAgentRunHandler,
    StartAgentRunHandler,
    UpdateAgentRunProgressHandler,
)
from app.infrastructure.database.repositories.agent_run_repository import (
    SqlAlchemyAgentRunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_agent_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Set the session factory for all agent activities.

    Called once during worker startup.
    """
    global _session_factory
    _session_factory = factory


def _get_session() -> AsyncSession:
    if _session_factory is None:
        msg = "Session factory not configured. Call configure_agent_session_factory first."
        raise RuntimeError(msg)
    return _session_factory()


# ---------------------------------------------------------------------------
# Activity input dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateAgentRunInput:
    """Input for the create_agent_run activity."""

    agent_name: str = ""
    agent_definition_id: str | None = None
    provider: str = ""
    model: str = ""
    tools: tuple[str, ...] = ()
    max_steps: int = 10
    timeout_seconds: int = 300
    project_id: str | None = None
    created_by: str | None = None
    tags: tuple[str, ...] = ()
    workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class RunIdInput:
    """Input for activities that only need a run ID."""

    run_id: str


@dataclass(frozen=True, slots=True)
class StartAgentRunInput:
    """Input for the start_agent_run activity."""

    run_id: str
    total_steps: int


@dataclass(frozen=True, slots=True)
class ProgressInput:
    """Input for the update_agent_run_progress activity."""

    run_id: str
    steps_completed: int = 0
    steps_failed: int = 0
    token_input: int = 0
    token_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class FailAgentRunInput:
    """Input for the fail_agent_run activity."""

    run_id: str
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelAgentRunInput:
    """Input for the cancel_agent_run activity."""

    run_id: str
    reason: str = "user_cancelled"
    force: bool = False


# ---------------------------------------------------------------------------
# Activity results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    """Result returned by agent run lifecycle activities."""

    run_id: str
    status: str
    agent_name: str = ""


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
async def create_agent_run_activity(input: CreateAgentRunInput) -> AgentRunResult:
    """Create a new agent run and return its ID."""
    activity.logger.info("Creating agent run name=%s", input.agent_name)
    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        handler = CreateAgentRunHandler(repo)
        command = CreateAgentRunCommand(
            agent_name=input.agent_name,
            agent_definition_id=input.agent_definition_id,
            provider=input.provider,
            model=input.model,
            tools=input.tools,
            max_steps=input.max_steps,
            timeout_seconds=input.timeout_seconds,
            project_id=input.project_id,
            created_by=input.created_by,
            tags=input.tags,
            workflow_id=input.workflow_id,
        )
        run = await handler.handle(command)
        await session.commit()
    return AgentRunResult(
        run_id=str(run.id),
        status=run.status.value,
        agent_name=run.agent_name,
    )


@activity.defn
async def queue_agent_run_activity(input: RunIdInput) -> AgentRunResult:
    """Transition a run to QUEUED status."""
    activity.logger.info("Queuing agent run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        handler = QueueAgentRunHandler(repo)
        command = QueueAgentRunCommand(run_id=input.run_id)
        run = await handler.handle(command)
        await session.commit()
    return AgentRunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def start_agent_run_activity(input: StartAgentRunInput) -> AgentRunResult:
    """Transition a run to RUNNING status."""
    activity.logger.info(
        "Starting agent run run_id=%s total_steps=%d",
        input.run_id,
        input.total_steps,
    )
    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        handler = StartAgentRunHandler(repo)
        command = StartAgentRunCommand(
            run_id=input.run_id,
            total_steps=input.total_steps,
        )
        run = await handler.handle(command)
        await session.commit()
    return AgentRunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def update_agent_run_progress_activity(input: ProgressInput) -> AgentRunResult:
    """Persist progress updates for a running agent."""
    activity.logger.debug(
        "Updating agent run progress run_id=%s completed=%d",
        input.run_id,
        input.steps_completed,
    )
    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        handler = UpdateAgentRunProgressHandler(repo)
        command = UpdateAgentRunProgressCommand(
            run_id=input.run_id,
            steps_completed=input.steps_completed,
            steps_failed=input.steps_failed,
            token_input=input.token_input,
            token_output=input.token_output,
            cost_usd=input.cost_usd,
            latency_ms=input.latency_ms,
        )
        run = await handler.handle(command)
        await session.commit()
    return AgentRunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def complete_agent_run_activity(input: RunIdInput) -> AgentRunResult:
    """Mark a run as completed."""
    activity.logger.info("Completing agent run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        handler = CompleteAgentRunHandler(repo)
        command = CompleteAgentRunCommand(run_id=input.run_id)
        run = await handler.handle(command)
        await session.commit()
    return AgentRunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def fail_agent_run_activity(input: FailAgentRunInput) -> AgentRunResult:
    """Mark a run as failed."""
    activity.logger.warning(
        "Failing agent run run_id=%s error_code=%s",
        input.run_id,
        input.error_code,
    )
    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        handler = FailAgentRunHandler(repo)
        command = FailAgentRunCommand(
            run_id=input.run_id,
            error_code=input.error_code,
            error_message=input.error_message,
        )
        run = await handler.handle(command)
        await session.commit()
    return AgentRunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def cancel_agent_run_activity(input: CancelAgentRunInput) -> AgentRunResult:
    """Cancel a running agent."""
    activity.logger.info("Cancelling agent run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        handler = CancelAgentRunHandler(repo)
        command = CancelAgentRunCommand(
            run_id=input.run_id,
            reason=input.reason,
            force=input.force,
        )
        run = await handler.handle(command)
        await session.commit()
    return AgentRunResult(run_id=str(run.id), status=run.status.value)
