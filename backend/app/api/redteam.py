"""Red Team & Safety API router."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_user, get_db_session
from app.infrastructure.database.repositories.attack_definition_repository import (
    SqlAlchemyAttackDefinitionRepository,
)
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.redteam.application.commands import (
    ActivateAttackDefinitionCommand,
    ArchiveAttackDefinitionCommand,
    CancelAttackRunCommand,
    CompleteAttackRunCommand,
    CreateAttackDefinitionCommand,
    CreateAttackRunCommand,
    DeleteAttackDefinitionCommand,
    FailAttackRunCommand,
    GetAttackDefinitionQuery,
    GetAttackRunQuery,
    ListAttackDefinitionsQuery,
    ListAttackRunsQuery,
    StartAttackRunCommand,
    UpdateAttackDefinitionCommand,
)
from app.redteam.application.handlers import (
    ActivateAttackDefinitionHandler,
    ArchiveAttackDefinitionHandler,
    CancelAttackRunHandler,
    CompleteAttackRunHandler,
    CreateAttackDefinitionHandler,
    CreateAttackRunHandler,
    DeleteAttackDefinitionHandler,
    FailAttackRunHandler,
    GetAttackDefinitionHandler,
    GetAttackRunHandler,
    ListAttackDefinitionsHandler,
    ListAttackRunsHandler,
    StartAttackRunHandler,
    UpdateAttackDefinitionHandler,
)
from app.redteam.domain.entities import AttackDefinition, AttackRun
from app.schemas.redteam import (
    AttackDefinitionListResponse,
    AttackDefinitionResponse,
    AttackDefinitionSummary,
    AttackRunListResponse,
    AttackRunResponse,
    AttackRunSummary,
    CreateAttackDefinitionRequest,
    CreateAttackRunRequest,
    FailAttackRunRequest,
    StartAttackRunRequest,
    UpdateAttackDefinitionRequest,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.dependencies import CurrentUser
    from app.redteam.contracts.repositories import PaginatedAttackDefinitions, PaginatedAttackRuns


redteam_router = APIRouter(prefix="/redteam", tags=["redteam"])


def _get_definition_repo(session: AsyncSession) -> SqlAlchemyAttackDefinitionRepository:
    return SqlAlchemyAttackDefinitionRepository(session)


def _get_run_repo(session: AsyncSession) -> SqlAlchemyAttackRunRepository:
    return SqlAlchemyAttackRunRepository(session)


def _definition_to_response(d: AttackDefinition) -> AttackDefinitionResponse:
    return AttackDefinitionResponse(
        id=str(d.id),
        name=d.name,
        description=d.description,
        category=d.category.value,
        severity=d.severity.value,
        status=d.status.value,
        prompt_template=d.template.prompt_template if d.template else "",
        system_prompt_override=d.template.system_prompt_override if d.template else None,
        expected_behavior=d.template.expected_behavior if d.template else "",
        parameters=dict(d.parameters or {}),
        tags=list(d.tags or []),
        created_by=d.created_by,
        version=d.version,
        created_at=_dt_str(d.created_at),
        updated_at=_dt_str(d.updated_at),
    )


def _definition_to_summary(d: AttackDefinition) -> AttackDefinitionSummary:
    return AttackDefinitionSummary(
        id=str(d.id),
        name=d.name,
        category=d.category.value,
        severity=d.severity.value,
        status=d.status.value,
        version=d.version,
        created_at=_dt_str(d.created_at),
        updated_at=_dt_str(d.updated_at),
    )


def _definitions_to_list(p: PaginatedAttackDefinitions) -> AttackDefinitionListResponse:
    return AttackDefinitionListResponse(
        items=[_definition_to_summary(i) for i in p.items],
        total=p.total,
        page=p.page,
        page_size=p.page_size,
        total_pages=p.total_pages,
    )


def _run_to_response(r: AttackRun) -> AttackRunResponse:
    return AttackRunResponse(
        id=str(r.id),
        evaluation_run_id=str(r.evaluation_run_id) if r.evaluation_run_id else None,
        status=r.status.value,
        attack_definition_ids=[str(did) for did in r.attack_definition_ids],
        configuration={},
        items_total=r.items_total,
        items_completed=r.items_completed,
        items_passed=r.items_passed,
        items_violated=r.items_violated,
        items_failed=r.items_failed,
        progress=r.progress,
        version=r.version,
        started_at=_dt_str(r.started_at) if r.started_at else None,
        completed_at=_dt_str(r.completed_at) if r.completed_at else None,
        created_at=_dt_str(r.created_at),
        updated_at=_dt_str(r.updated_at),
    )


def _run_to_summary(r: AttackRun) -> AttackRunSummary:
    return AttackRunSummary(
        id=str(r.id),
        evaluation_run_id=str(r.evaluation_run_id) if r.evaluation_run_id else None,
        status=r.status.value,
        items_total=r.items_total,
        items_completed=r.items_completed,
        progress=r.progress,
        version=r.version,
        created_at=_dt_str(r.created_at),
        updated_at=_dt_str(r.updated_at),
    )


def _runs_to_list(p: PaginatedAttackRuns) -> AttackRunListResponse:
    return AttackRunListResponse(
        items=[_run_to_summary(i) for i in p.items],
        total=p.total,
        page=p.page,
        page_size=p.page_size,
        total_pages=p.total_pages,
    )


def _dt_str(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


# --- Attack Definition Endpoints ---

@redteam_router.post("/definitions", response_model=AttackDefinitionResponse, status_code=201)
async def create_attack_definition(
    body: CreateAttackDefinitionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackDefinitionResponse:
    repo = _get_definition_repo(session)
    handler = CreateAttackDefinitionHandler(repo)
    command = CreateAttackDefinitionCommand(
        name=body.name,
        description=body.description,
        category=body.category,
        severity=body.severity,
        prompt_template=body.prompt_template,
        system_prompt_override=body.system_prompt_override,
        expected_behavior=body.expected_behavior,
        parameters=dict(body.parameters),
        tags=tuple(body.tags),
        created_by=body.created_by,
    )
    try:
        definition = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _definition_to_response(definition)


@redteam_router.get("/definitions", response_model=AttackDefinitionListResponse)
async def list_attack_definitions(
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackDefinitionListResponse:
    repo = _get_definition_repo(session)
    handler = ListAttackDefinitionsHandler(repo)
    query = ListAttackDefinitionsQuery(
        category=category,
        severity=severity,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    result = await handler.handle(query)
    return _definitions_to_list(result)


@redteam_router.get("/definitions/{definition_id}", response_model=AttackDefinitionResponse)
async def get_attack_definition(
    definition_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackDefinitionResponse:
    repo = _get_definition_repo(session)
    handler = GetAttackDefinitionHandler(repo)
    query = GetAttackDefinitionQuery(definition_id=definition_id)
    try:
        definition = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _definition_to_response(definition)


@redteam_router.patch("/definitions/{definition_id}", response_model=AttackDefinitionResponse)
async def update_attack_definition(
    definition_id: str,
    body: UpdateAttackDefinitionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackDefinitionResponse:
    repo = _get_definition_repo(session)
    handler = UpdateAttackDefinitionHandler(repo)
    command = UpdateAttackDefinitionCommand(
        definition_id=definition_id,
        name=body.name,
        description=body.description,
        category=body.category,
        severity=body.severity,
        prompt_template=body.prompt_template,
        system_prompt_override=body.system_prompt_override,
        expected_behavior=body.expected_behavior,
        parameters=dict(body.parameters) if body.parameters is not None else None,
        tags=tuple(body.tags) if body.tags is not None else None,
    )
    try:
        definition = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _definition_to_response(definition)


@redteam_router.delete("/definitions/{definition_id}", status_code=204)
async def delete_attack_definition(
    definition_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    repo = _get_definition_repo(session)
    handler = DeleteAttackDefinitionHandler(repo)
    command = DeleteAttackDefinitionCommand(definition_id=definition_id)
    try:
        await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@redteam_router.post("/definitions/{definition_id}/activate", response_model=AttackDefinitionResponse)
async def activate_attack_definition(
    definition_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackDefinitionResponse:
    repo = _get_definition_repo(session)
    handler = ActivateAttackDefinitionHandler(repo)
    command = ActivateAttackDefinitionCommand(definition_id=definition_id)
    try:
        definition = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _definition_to_response(definition)


@redteam_router.post("/definitions/{definition_id}/archive", response_model=AttackDefinitionResponse)
async def archive_attack_definition(
    definition_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackDefinitionResponse:
    repo = _get_definition_repo(session)
    handler = ArchiveAttackDefinitionHandler(repo)
    command = ArchiveAttackDefinitionCommand(definition_id=definition_id)
    try:
        definition = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _definition_to_response(definition)


# --- Attack Run Endpoints ---

@redteam_router.post("/runs", response_model=AttackRunResponse, status_code=201)
async def create_attack_run(
    body: CreateAttackRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackRunResponse:
    repo = _get_run_repo(session)
    handler = CreateAttackRunHandler(repo)
    command = CreateAttackRunCommand(
        evaluation_run_id=body.evaluation_run_id,
        attack_definition_ids=tuple(body.attack_definition_ids),
        configuration=dict(body.configuration),
    )
    try:
        run = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@redteam_router.get("/runs", response_model=AttackRunListResponse)
async def list_attack_runs(
    status: str | None = Query(default=None),
    evaluation_run_id: str | None = Query(default=None),
    category: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackRunListResponse:
    repo = _get_run_repo(session)
    handler = ListAttackRunsHandler(repo)
    query = ListAttackRunsQuery(
        status=status,
        evaluation_run_id=evaluation_run_id,
        category=category,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    result = await handler.handle(query)
    return _runs_to_list(result)


@redteam_router.get("/runs/{run_id}", response_model=AttackRunResponse)
async def get_attack_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackRunResponse:
    repo = _get_run_repo(session)
    handler = GetAttackRunHandler(repo)
    query = GetAttackRunQuery(run_id=run_id)
    try:
        run = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@redteam_router.post("/runs/{run_id}/start", response_model=AttackRunResponse)
async def start_attack_run(
    run_id: str,
    body: StartAttackRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackRunResponse:
    repo = _get_run_repo(session)
    handler = StartAttackRunHandler(repo)
    command = StartAttackRunCommand(run_id=run_id, total_items=body.total_items)
    try:
        run = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@redteam_router.post("/runs/{run_id}/complete", response_model=AttackRunResponse)
async def complete_attack_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackRunResponse:
    repo = _get_run_repo(session)
    handler = CompleteAttackRunHandler(repo)
    command = CompleteAttackRunCommand(run_id=run_id)
    try:
        run = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@redteam_router.post("/runs/{run_id}/fail", response_model=AttackRunResponse)
async def fail_attack_run(
    run_id: str,
    body: FailAttackRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackRunResponse:
    repo = _get_run_repo(session)
    handler = FailAttackRunHandler(repo)
    command = FailAttackRunCommand(run_id=run_id, error_message=body.error_message)
    try:
        run = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@redteam_router.post("/runs/{run_id}/cancel", response_model=AttackRunResponse)
async def cancel_attack_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> AttackRunResponse:
    repo = _get_run_repo(session)
    handler = CancelAttackRunHandler(repo)
    command = CancelAttackRunCommand(run_id=run_id)
    try:
        run = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)
