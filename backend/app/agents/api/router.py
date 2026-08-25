"""REST endpoints for agent run management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from app.agents.application.run_commands import (
    CancelAgentRunCommand,
    CreateAgentRunCommand,
    GetAgentRunQuery,
    ListAgentRunsQuery,
    QueueAgentRunCommand,
    RetryAgentRunCommand,
)
from app.agents.application.run_handlers import (
    CancelAgentRunHandler,
    CreateAgentRunHandler,
    GetAgentRunHandler,
    ListAgentRunsHandler,
    QueueAgentRunHandler,
    RetryAgentRunHandler,
)
from app.agents.temporal.workflow import AgentRunWorkflow, AgentRunWorkflowInput
from app.core.config import AppConfig
from app.core.dependencies import (
    CurrentUser,
    get_config_dependency,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.infrastructure.database.repositories.agent_run_repository import (
    SqlAlchemyAgentRunRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.schemas.agent_run import (
    AgentRunListResponse,
    AgentRunResponse,
    AgentRunSummaryResponse,
    CancelAgentRunRequest,
    CreateAgentRunRequest,
)

if TYPE_CHECKING:
    from app.agents.domain.contracts.agent_contracts import PaginatedAgentRuns
    from app.agents.domain.entities.agent_entities import AgentRun

agent_run_router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def _get_repository(session: AsyncSession) -> SqlAlchemyAgentRunRepository:
    return SqlAlchemyAgentRunRepository(session)


def _run_to_response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        id=str(run.id),
        agent_definition_id=run.agent_definition_id,
        agent_name=run.agent_name,
        workflow_id=run.workflow_id,
        provider=run.config.profile.provider_name,
        model=run.config.profile.model_id,
        status=run.status.value,
        priority=run.priority.value,
        steps_total=run.steps_total,
        steps_completed=run.steps_completed,
        steps_failed=run.steps_failed,
        progress=run.progress,
        token_input=run.token_input,
        token_output=run.token_output,
        total_tokens=run.total_tokens,
        cost=run.cost,
        average_latency_ms=run.average_latency_ms,
        failure_reason=run.failure_summary.value if run.failure_summary is not None else None,
        version=run.version,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        cancelled_at=run.cancelled_at.isoformat() if run.cancelled_at else None,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


def _run_to_summary(run: AgentRun) -> AgentRunSummaryResponse:
    return AgentRunSummaryResponse(
        id=str(run.id),
        agent_definition_id=run.agent_definition_id,
        agent_name=run.agent_name,
        provider=run.config.profile.provider_name,
        model=run.config.profile.model_id,
        status=run.status.value,
        progress=run.progress,
        steps_total=run.steps_total,
        steps_completed=run.steps_completed,
        steps_failed=run.steps_failed,
        cost=run.cost,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_at=run.created_at.isoformat(),
    )


def _to_list_response(paginated: PaginatedAgentRuns) -> AgentRunListResponse:
    return AgentRunListResponse(
        items=[_run_to_summary(i) for i in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        total_pages=paginated.total_pages,
    )


@agent_run_router.post("", response_model=AgentRunResponse, status_code=201)
async def create_agent_run(
    body: CreateAgentRunRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    temporal_client: TemporalClient = Depends(get_temporal_client),
    config: AppConfig = Depends(get_config_dependency),
) -> AgentRunResponse:
    """Create a new agent run and schedule its execution."""
    repo = _get_repository(session)
    handler = CreateAgentRunHandler(repo)
    command = CreateAgentRunCommand(
        agent_name=body.agent_name,
        agent_definition_id=body.agent_definition_id,
        provider=body.provider,
        model=body.model,
        tools=tuple(body.tools),
        max_steps=body.max_steps,
        timeout_seconds=body.timeout_seconds,
        project_id=body.project_id,
        created_by=current_user.user_id,
        tags=tuple(body.tags),
        workflow_id=body.workflow_id,
    )
    try:
        run = await handler.handle(command)
        await session.flush()

        workflow_id = f"agent-run-{run.id}"
        await temporal_client.start_workflow(
            AgentRunWorkflow.run,
            AgentRunWorkflowInput(
                run_id=str(run.id),
                total_steps=body.max_steps,
            ),
            id=workflow_id,
            task_queue=config.temporal_task_queue,
        )

        queue_handler = QueueAgentRunHandler(repo)
        queue_command = QueueAgentRunCommand(run_id=str(run.id))
        run = await queue_handler.handle(queue_command)
        run.workflow_id = workflow_id
        await repo.save(run)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@agent_run_router.get("", response_model=AgentRunListResponse)
async def list_agent_runs(
    agent_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentRunListResponse:
    """List agent runs with filtering, sorting, and pagination."""
    repo = _get_repository(session)
    handler = ListAgentRunsHandler(repo)
    query = ListAgentRunsQuery(
        agent_name=agent_name,
        status=status,
        provider=provider,
        model=model,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    result = await handler.handle(query)
    return _to_list_response(result)


@agent_run_router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentRunResponse:
    """Get an agent run by ID."""
    repo = _get_repository(session)
    handler = GetAgentRunHandler(repo)
    query = GetAgentRunQuery(run_id=run_id)
    try:
        run = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@agent_run_router.post("/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent_run(
    run_id: str,
    body: CancelAgentRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    temporal_client: TemporalClient = Depends(get_temporal_client),
) -> AgentRunResponse:
    """Cancel an agent run."""
    repo = _get_repository(session)
    handler = CancelAgentRunHandler(repo)
    command = CancelAgentRunCommand(
        run_id=run_id,
        reason=body.reason,
        force=body.force,
    )
    try:
        run = await handler.handle(command)
        if run.workflow_id:
            try:
                handle = temporal_client.get_workflow_handle(run.workflow_id)
                await handle.signal(AgentRunWorkflow.cancel)
            except Exception:
                pass
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@agent_run_router.post("/{run_id}/retry", response_model=AgentRunResponse, status_code=201)
async def retry_agent_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentRunResponse:
    """Retry a failed agent run."""
    repo = _get_repository(session)
    handler = RetryAgentRunHandler(repo)
    command = RetryAgentRunCommand(run_id=run_id)
    try:
        run = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)
