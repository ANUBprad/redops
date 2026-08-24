"""Temporal activities for agent run execution.

Activities call the existing application handlers, ensuring no
duplicate business logic. Each activity creates its own database
session via the configured session factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
from app.agents.domain.tool_execution import ToolRegistry
from app.infrastructure.database.repositories.agent_run_repository import (
    SqlAlchemyAgentRunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_session_factory: async_sessionmaker[AsyncSession] | None = None
_agent_provider_registry: Any = None


def configure_agent_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Set the session factory for all agent activities.

    Called once during worker startup.
    """
    global _session_factory
    _session_factory = factory


def configure_agent_provider_registry(registry: Any) -> None:
    """Set the provider registry for agent loop execution."""
    global _agent_provider_registry
    _agent_provider_registry = registry


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


# ---------------------------------------------------------------------------
# Agent loop execution activity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExecuteAgentLoopInput:
    """Input for the execute_agent_loop activity."""

    run_id: str
    provider_name: str = ""
    model_id: str = ""
    system_prompt: str = ""
    tools: tuple[str, ...] = ()
    max_steps: int = 10


@dataclass(frozen=True, slots=True)
class ExecuteAgentLoopResult:
    """Result returned by the agent loop execution activity."""

    run_id: str
    success: bool = True
    final_response: str = ""
    total_steps: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    error: str | None = None
    status: str = "completed"


@activity.defn
async def execute_agent_loop_activity(
    input: ExecuteAgentLoopInput,
) -> ExecuteAgentLoopResult:
    """Execute the full agent loop (LLM ↔ tool interaction).

    Creates a provider from the configured registry, builds a tool
    registry, and runs AgentLoop.execute_sync(). Returns the full
    loop result including trajectory metrics.

    Heartbeats are sent before each LLM call and after each tool
    execution so Temporal can detect stuck activities and honour
    cancellation requests.
    """
    activity.logger.info(
        "Executing agent loop run_id=%s provider=%s model=%s",
        input.run_id,
        input.provider_name,
        input.model_id,
    )

    if _agent_provider_registry is None:
        msg = "Provider registry not configured. Call configure_agent_provider_registry first."
        raise RuntimeError(msg)

    provider = _agent_provider_registry.resolve(input.provider_name)

    tool_registry = ToolRegistry()

    from app.agents.runtime.executor import AgentExecutor

    executor = AgentExecutor(provider, tool_registry)

    activity.heartbeat(f"agent loop starting run_id={input.run_id}")

    # Set up cancellation monitoring: a threading.Event that is set
    # when Temporal reports the activity has been cancelled.
    import threading

    cancel_event = threading.Event()

    def _monitor_cancellation() -> None:
        """Poll activity.is_cancelled() and signal the cancel event."""
        while not cancel_event.is_set():
            if activity.is_cancelled():
                cancel_event.set()
                return
            cancel_event.wait(timeout=1.0)

    monitor_thread = threading.Thread(target=_monitor_cancellation, daemon=True)
    monitor_thread.start()

    async with _get_session() as session:
        repo = SqlAlchemyAgentRunRepository(session)
        from app.kernel.entities.base import UUIDv7

        run = await repo.find_by_id(UUIDv7.from_string(input.run_id))
        if run is None:
            msg = f"Agent run {input.run_id} not found"
            raise ValueError(msg)

        loop_result = executor.execute_run_sync(
            run, system_prompt=input.system_prompt, cancel_event=cancel_event
        )

        # Stop the cancellation monitor thread
        cancel_event.set()
        monitor_thread.join(timeout=2.0)

        activity.heartbeat(f"agent loop finished run_id={input.run_id}")

        if loop_result.success:
            complete_handler = CompleteAgentRunHandler(repo)
            complete_command = CompleteAgentRunCommand(run_id=input.run_id)
            await complete_handler.handle(complete_command)
        else:
            fail_handler = FailAgentRunHandler(repo)
            fail_command = FailAgentRunCommand(
                run_id=input.run_id,
                error_code="EXECUTION_FAILED",
                error_message=loop_result.error or "Agent loop failed",
            )
            await fail_handler.handle(fail_command)

        await session.commit()

    return ExecuteAgentLoopResult(
        run_id=input.run_id,
        success=loop_result.success,
        final_response=loop_result.final_response,
        total_steps=loop_result.total_steps,
        total_llm_calls=loop_result.total_llm_calls,
        total_tool_calls=loop_result.total_tool_calls,
        total_tokens_input=loop_result.total_tokens_input,
        total_tokens_output=loop_result.total_tokens_output,
        total_cost_usd=loop_result.total_cost_usd,
        total_duration_ms=loop_result.total_duration_ms,
        error=loop_result.error,
        status=loop_result.status,
    )
