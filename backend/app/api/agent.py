"""REST endpoints for agent management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.application.commands import (
    ActivateAgentCommand,
    ArchiveAgentCommand,
    CreateAgentCommand,
    DeactivateAgentCommand,
    DeleteAgentCommand,
    GetAgentQuery,
    ListAgentsQuery,
    UpdateAgentCommand,
)
from app.agent.application.handlers import (
    ActivateAgentHandler,
    ArchiveAgentHandler,
    CreateAgentHandler,
    DeactivateAgentHandler,
    DeleteAgentHandler,
    GetAgentHandler,
    ListAgentsHandler,
    UpdateAgentHandler,
)
from app.agent.domain.entities.agent_definition import AgentDefinition
from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.repositories.agent_repository import (
    SqlAlchemyAgentDefinitionRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.schemas.agent import (
    AgentListResponse,
    AgentResponse,
    AgentSummaryResponse,
    CreateAgentRequest,
    UpdateAgentRequest,
)

if TYPE_CHECKING:
    from app.agent.domain.contracts.agent_contracts import PaginatedAgents

agent_router = APIRouter(prefix="/agents", tags=["agents"])


def _get_repository(session: AsyncSession) -> SqlAlchemyAgentDefinitionRepository:
    """Create a repository from the database session."""
    return SqlAlchemyAgentDefinitionRepository(session)


def _agent_to_response(agent: AgentDefinition) -> AgentResponse:
    """Convert a domain AgentDefinition to an API response."""
    return AgentResponse(
        id=str(agent.id),
        project_id=agent.project_id,
        name=str(agent.name.value),
        description=agent.description.value if agent.description is not None else None,
        agent_type=agent.agent_type.value,
        model=agent.model,
        provider=agent.provider,
        capabilities=list(agent.capabilities),
        config=dict(agent.config),
        endpoint=agent.endpoint.value if agent.endpoint is not None else None,
        status=agent.status.value,
        created_by=agent.created_by,
        version=agent.version,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
    )


def _agent_to_summary(agent: AgentDefinition) -> AgentSummaryResponse:
    """Convert a domain AgentDefinition to a summary response."""
    return AgentSummaryResponse(
        id=str(agent.id),
        project_id=agent.project_id,
        name=str(agent.name.value),
        agent_type=agent.agent_type.value,
        model=agent.model,
        provider=agent.provider,
        status=agent.status.value,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
    )


def _to_list_response(paginated: PaginatedAgents) -> AgentListResponse:
    """Convert paginated agents to list response."""
    return AgentListResponse(
        items=[_agent_to_summary(i) for i in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        total_pages=paginated.total_pages,
    )


@agent_router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: CreateAgentRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Create a new agent definition."""
    repo = _get_repository(session)
    handler = CreateAgentHandler(repo)
    command = CreateAgentCommand(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        agent_type=body.agent_type,
        model=body.model,
        provider=body.provider,
        capabilities=tuple(body.capabilities),
        config=body.config,
        endpoint=body.endpoint,
        created_by=body.created_by,
    )
    try:
        agent = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _agent_to_response(agent)


@agent_router.get("", response_model=AgentListResponse)
async def list_agents(
    project_id: str | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentListResponse:
    """List agents with filtering, sorting, and pagination."""
    repo = _get_repository(session)
    handler = ListAgentsHandler(repo)
    query = ListAgentsQuery(
        project_id=project_id,
        agent_type=agent_type,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    result = await handler.handle(query)
    return _to_list_response(result)


@agent_router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Get an agent by ID."""
    repo = _get_repository(session)
    handler = GetAgentHandler(repo)
    query = GetAgentQuery(agent_id=agent_id)
    try:
        agent = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _agent_to_response(agent)


@agent_router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: UpdateAgentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Update an agent definition."""
    repo = _get_repository(session)
    handler = UpdateAgentHandler(repo)
    command = UpdateAgentCommand(
        agent_id=agent_id,
        name=body.name,
        description=body.description,
        agent_type=body.agent_type,
        model=body.model,
        provider=body.provider,
        capabilities=tuple(body.capabilities) if body.capabilities is not None else None,
        config=body.config,
        endpoint=body.endpoint,
    )
    try:
        agent = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _agent_to_response(agent)


@agent_router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an agent definition."""
    repo = _get_repository(session)
    handler = DeleteAgentHandler(repo)
    command = DeleteAgentCommand(agent_id=agent_id)
    try:
        await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@agent_router.post("/{agent_id}/activate", response_model=AgentResponse)
async def activate_agent(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Activate an agent definition."""
    repo = _get_repository(session)
    handler = ActivateAgentHandler(repo)
    command = ActivateAgentCommand(agent_id=agent_id)
    try:
        agent = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _agent_to_response(agent)


@agent_router.post("/{agent_id}/deactivate", response_model=AgentResponse)
async def deactivate_agent(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Deactivate an agent definition."""
    repo = _get_repository(session)
    handler = DeactivateAgentHandler(repo)
    command = DeactivateAgentCommand(agent_id=agent_id)
    try:
        agent = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _agent_to_response(agent)


@agent_router.post("/{agent_id}/archive", response_model=AgentResponse)
async def archive_agent(
    agent_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AgentResponse:
    """Archive an agent definition."""
    repo = _get_repository(session)
    handler = ArchiveAgentHandler(repo)
    command = ArchiveAgentCommand(agent_id=agent_id)
    try:
        agent = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _agent_to_response(agent)
