"""Temporal activities for evaluation run execution.

Activities call the existing application handlers, ensuring no
duplicate business logic. Each activity creates its own database
session via the configured session factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from temporalio import activity

from app.evaluation.application.run_commands import (
    CancelEvaluationRunCommand,
    CompleteEvaluationRunCommand,
    CreateEvaluationRunCommand,
    FailEvaluationRunCommand,
    QueueEvaluationRunCommand,
    StartEvaluationRunCommand,
    UpdateRunProgressCommand,
)
from app.evaluation.application.run_handlers import (
    CancelEvaluationRunHandler,
    CompleteEvaluationRunHandler,
    CreateEvaluationRunHandler,
    FailEvaluationRunHandler,
    QueueEvaluationRunHandler,
    StartEvaluationRunHandler,
    UpdateRunProgressHandler,
)
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Set the session factory for all activities.

    Called once during worker startup.
    """
    global _session_factory
    _session_factory = factory


def _get_session() -> AsyncSession:
    """Get a new database session."""
    if _session_factory is None:
        msg = "Session factory not configured. Call configure_session_factory first."
        raise RuntimeError(msg)
    return _session_factory()


# ---------------------------------------------------------------------------
# Activity input dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateRunInput:
    """Input for the create_run activity."""

    evaluation_id: str | None = None
    evaluation_name: str = ""
    provider: str = ""
    model: str = ""
    metrics: tuple[str, ...] = ()
    project_id: str | None = None
    created_by: str | None = None
    tags: tuple[str, ...] = ()
    workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class RunIdInput:
    """Input for activities that only need a run ID."""

    run_id: str


@dataclass(frozen=True, slots=True)
class StartRunInput:
    """Input for the start_run activity."""

    run_id: str
    total_items: int


@dataclass(frozen=True, slots=True)
class ProgressInput:
    """Input for the update_progress activity."""

    run_id: str
    items_completed: int = 0
    items_failed: int = 0
    token_input: int = 0
    token_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class FailRunInput:
    """Input for the fail_run activity."""

    run_id: str
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelRunInput:
    """Input for the cancel_run activity."""

    run_id: str
    reason: str = "user_cancelled"
    force: bool = False


# ---------------------------------------------------------------------------
# Activity results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunResult:
    """Result returned by run lifecycle activities."""

    run_id: str
    status: str
    evaluation_name: str = ""


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
async def create_run_activity(input: CreateRunInput) -> RunResult:
    """Create a new evaluation run and return its ID."""
    activity.logger.info("Creating evaluation run name=%s", input.evaluation_name)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_id=input.evaluation_id,
            evaluation_name=input.evaluation_name,
            provider=input.provider,
            model=input.model,
            metrics=input.metrics,
            project_id=input.project_id,
            created_by=input.created_by,
            tags=input.tags,
            workflow_id=input.workflow_id,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(
        run_id=str(run.id),
        status=run.status.value,
        evaluation_name=run.evaluation_name,
    )


@activity.defn
async def queue_run_activity(input: RunIdInput) -> RunResult:
    """Transition a run to QUEUED status."""
    activity.logger.info("Queuing evaluation run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = QueueEvaluationRunHandler(repo)
        command = QueueEvaluationRunCommand(run_id=input.run_id)
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def start_run_activity(input: StartRunInput) -> RunResult:
    """Transition a run to RUNNING status."""
    activity.logger.info(
        "Starting evaluation run run_id=%s total_items=%d",
        input.run_id,
        input.total_items,
    )
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = StartEvaluationRunHandler(repo)
        command = StartEvaluationRunCommand(
            run_id=input.run_id,
            total_items=input.total_items,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def update_progress_activity(input: ProgressInput) -> RunResult:
    """Persist progress updates for a running evaluation."""
    activity.logger.debug(
        "Updating run progress run_id=%s completed=%d",
        input.run_id,
        input.items_completed,
    )
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = UpdateRunProgressHandler(repo)
        command = UpdateRunProgressCommand(
            run_id=input.run_id,
            items_completed=input.items_completed,
            items_failed=input.items_failed,
            token_input=input.token_input,
            token_output=input.token_output,
            cost_usd=input.cost_usd,
            latency_ms=input.latency_ms,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def complete_run_activity(input: RunIdInput) -> RunResult:
    """Mark a run as completed."""
    activity.logger.info("Completing evaluation run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CompleteEvaluationRunHandler(repo)
        command = CompleteEvaluationRunCommand(run_id=input.run_id)
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def fail_run_activity(input: FailRunInput) -> RunResult:
    """Mark a run as failed."""
    activity.logger.warning(
        "Failing evaluation run run_id=%s error_code=%s",
        input.run_id,
        input.error_code,
    )
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = FailEvaluationRunHandler(repo)
        command = FailEvaluationRunCommand(
            run_id=input.run_id,
            error_code=input.error_code,
            error_message=input.error_message,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)


@activity.defn
async def cancel_run_activity(input: CancelRunInput) -> RunResult:
    """Cancel a running evaluation."""
    activity.logger.info("Cancelling evaluation run run_id=%s", input.run_id)
    async with _get_session() as session:
        repo = SqlAlchemyEvaluationRunRepository(session)
        handler = CancelEvaluationRunHandler(repo)
        command = CancelEvaluationRunCommand(
            run_id=input.run_id,
            reason=input.reason,
            force=input.force,
        )
        run = await handler.handle(command)
        await session.commit()
    return RunResult(run_id=str(run.id), status=run.status.value)
