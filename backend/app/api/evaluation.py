"""REST endpoints for evaluation management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
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
from app.evaluation.application.handlers import (
    ArchiveEvaluationHandler,
    CreateEvaluationHandler,
    DeleteEvaluationHandler,
    DuplicateEvaluationHandler,
    GetEvaluationHandler,
    ListEvaluationsHandler,
    MarkReadyEvaluationHandler,
    UpdateEvaluationHandler,
)
from app.infrastructure.database.repositories.evaluation_repository import (
    SqlAlchemyEvaluationRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.schemas.evaluation import (
    CreateEvaluationRequest,
    DuplicateEvaluationRequest,
    EvaluationListResponse,
    EvaluationResponse,
    EvaluationSummaryResponse,
    UpdateEvaluationRequest,
)

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import PaginatedEvaluations
    from app.evaluation.domain.entities.evaluation_definition import Evaluation

evaluation_router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def _get_repository(session: AsyncSession) -> SqlAlchemyEvaluationRepository:
    """Create a repository from the database session."""
    return SqlAlchemyEvaluationRepository(session)


def _evaluation_to_response(evaluation: Evaluation) -> EvaluationResponse:
    """Convert a domain Evaluation to an API response."""
    return EvaluationResponse(
        id=str(evaluation.id),
        project_id=evaluation.project_id,
        dataset_id=evaluation.dataset_id,
        name=str(evaluation.name.value),
        description=evaluation.description.value if evaluation.description is not None else None,
        provider=str(evaluation.provider.value),
        model=evaluation.model,
        metrics=[m.value for m in evaluation.metrics],
        tags=list(evaluation.tags),
        configuration=dict(evaluation.configuration),
        status=evaluation.status.value,
        created_by=evaluation.created_by,
        version=evaluation.version,
        created_at=evaluation.created_at.isoformat(),
        updated_at=evaluation.updated_at.isoformat(),
    )


def _evaluation_to_summary(evaluation: Evaluation) -> EvaluationSummaryResponse:
    """Convert a domain Evaluation to a summary response."""
    return EvaluationSummaryResponse(
        id=str(evaluation.id),
        project_id=evaluation.project_id,
        name=str(evaluation.name.value),
        provider=str(evaluation.provider.value),
        model=evaluation.model,
        status=evaluation.status.value,
        tags=list(evaluation.tags),
        created_at=evaluation.created_at.isoformat(),
        updated_at=evaluation.updated_at.isoformat(),
    )


def _to_list_response(paginated: PaginatedEvaluations) -> EvaluationListResponse:
    """Convert paginated evaluations to list response."""
    return EvaluationListResponse(
        items=[_evaluation_to_summary(i) for i in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        total_pages=paginated.total_pages,
    )


@evaluation_router.post("", response_model=EvaluationResponse, status_code=201)
async def create_evaluation(
    body: CreateEvaluationRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Create a new evaluation definition."""
    repo = _get_repository(session)
    handler = CreateEvaluationHandler(repo)
    command = CreateEvaluationCommand(
        project_id=body.project_id,
        dataset_id=body.dataset_id,
        name=body.name,
        description=body.description,
        provider=body.provider,
        model=body.model,
        metrics=tuple(body.metrics),
        tags=tuple(body.tags),
        configuration=body.configuration,
        created_by=body.created_by,
    )
    try:
        evaluation = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _evaluation_to_response(evaluation)


@evaluation_router.get("", response_model=EvaluationListResponse)
async def list_evaluations(
    project_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationListResponse:
    """List evaluations with filtering, sorting, and pagination."""
    repo = _get_repository(session)
    handler = ListEvaluationsHandler(repo)
    query = ListEvaluationsQuery(
        project_id=project_id,
        provider=provider,
        model=model,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    result = await handler.handle(query)
    return _to_list_response(result)


@evaluation_router.get("/{evaluation_id}", response_model=EvaluationResponse)
async def get_evaluation(
    evaluation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Get an evaluation by ID."""
    repo = _get_repository(session)
    handler = GetEvaluationHandler(repo)
    query = GetEvaluationQuery(evaluation_id=evaluation_id)
    try:
        evaluation = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _evaluation_to_response(evaluation)


@evaluation_router.patch("/{evaluation_id}", response_model=EvaluationResponse)
async def update_evaluation(
    evaluation_id: str,
    body: UpdateEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Update an evaluation definition."""
    repo = _get_repository(session)
    handler = UpdateEvaluationHandler(repo)
    command = UpdateEvaluationCommand(
        evaluation_id=evaluation_id,
        name=body.name,
        description=body.description,
        provider=body.provider,
        model=body.model,
        metrics=tuple(body.metrics) if body.metrics is not None else None,
        tags=tuple(body.tags) if body.tags is not None else None,
        configuration=body.configuration,
        dataset_id=body.dataset_id,
    )
    try:
        evaluation = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _evaluation_to_response(evaluation)


@evaluation_router.delete("/{evaluation_id}", status_code=204)
async def delete_evaluation(
    evaluation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an evaluation definition."""
    repo = _get_repository(session)
    handler = DeleteEvaluationHandler(repo)
    command = DeleteEvaluationCommand(evaluation_id=evaluation_id)
    try:
        await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@evaluation_router.post(
    "/{evaluation_id}/duplicate",
    response_model=EvaluationResponse,
    status_code=201,
)
async def duplicate_evaluation(
    evaluation_id: str,
    body: DuplicateEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Duplicate an evaluation definition."""
    repo = _get_repository(session)
    handler = DuplicateEvaluationHandler(repo)
    command = DuplicateEvaluationCommand(
        evaluation_id=evaluation_id,
        new_name=body.name,
    )
    try:
        evaluation = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _evaluation_to_response(evaluation)


@evaluation_router.post("/{evaluation_id}/archive", response_model=EvaluationResponse)
async def archive_evaluation(
    evaluation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Archive an evaluation definition."""
    repo = _get_repository(session)
    handler = ArchiveEvaluationHandler(repo)
    command = ArchiveEvaluationCommand(evaluation_id=evaluation_id)
    try:
        evaluation = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _evaluation_to_response(evaluation)


@evaluation_router.post("/{evaluation_id}/ready", response_model=EvaluationResponse)
async def mark_ready_evaluation(
    evaluation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationResponse:
    """Mark an evaluation as ready."""
    repo = _get_repository(session)
    handler = MarkReadyEvaluationHandler(repo)
    command = MarkReadyEvaluationCommand(evaluation_id=evaluation_id)
    try:
        evaluation = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _evaluation_to_response(evaluation)
