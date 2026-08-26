"""REST endpoints for Experiment management."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
)
from app.evaluation.domain.contracts.experiment_contracts import ExperimentQuery
from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.evaluation.services.experiment_service import ExperimentService
from app.infrastructure.database.repositories.experiment_repository import (
    SqlAlchemyExperimentRepository,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import BaseError

experiment_router = APIRouter(prefix="/experiments", tags=["experiments"])


def _get_service(session: AsyncSession) -> ExperimentService:
    """Create a service from the database session."""
    return ExperimentService(SqlAlchemyExperimentRepository(session))


# --- Schemas ---


class CreateExperimentRequest(BaseModel):
    """Request body for creating an experiment."""

    name: str = Field(..., min_length=1, max_length=255, description="Experiment name")
    description: str | None = Field(default=None, description="Description")
    hypothesis: str | None = Field(default=None, description="Hypothesis text")
    tags: list[str] = Field(default_factory=list, description="Tags")


class UpdateExperimentRequest(BaseModel):
    """Request body for updating an experiment."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    hypothesis: str | None = None
    conclusion: str | None = None
    tags: list[str] | None = None


class SetBaselineRequest(BaseModel):
    """Request body for setting baseline run."""

    run_id: str = Field(..., description="Evaluation run ID to use as baseline")


class ExperimentResponse(BaseModel):
    """Response model for an experiment."""

    id: str
    project_id: str
    name: str
    description: str | None = None
    hypothesis: str | None = None
    status: str
    baseline_run_id: str | None = None
    conclusion: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_by: str | None = None
    version: int
    created_at: str
    updated_at: str


class ExperimentListResponse(BaseModel):
    """Paginated list response for experiments."""

    items: list[ExperimentResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    total_pages: int


def _to_response(experiment: Any) -> ExperimentResponse:
    """Convert domain experiment to API response."""
    return ExperimentResponse(
        id=str(experiment.id),
        project_id=experiment.project_id,
        name=str(experiment.name.value),
        description=experiment.description.value if experiment.description else None,
        hypothesis=experiment.hypothesis,
        status=experiment.status.value,
        baseline_run_id=experiment.baseline_run_id,
        conclusion=experiment.conclusion,
        tags=list(experiment.tags),
        created_by=experiment.created_by,
        version=experiment.version,
        created_at=experiment.created_at.isoformat(),
        updated_at=experiment.updated_at.isoformat(),
    )


# --- Endpoints ---


@experiment_router.post("", response_model=ExperimentResponse, status_code=201)
async def create_experiment(
    body: CreateExperimentRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExperimentResponse:
    """Create a new experiment."""
    service = _get_service(session)
    try:
        experiment = await service.create_experiment(
            project_id=str(current_user.org_id) if current_user.org_id else "",
            name=body.name,
            description=body.description,
            hypothesis=body.hypothesis,
            tags=tuple(body.tags),
            created_by=current_user.user_id,
        )
        await session.commit()
        return _to_response(experiment)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@experiment_router.get("", response_model=ExperimentListResponse)
async def list_experiments(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    status: str | None = Query(default=None, description="Filter by status"),
    search: str | None = Query(default=None, description="Search by name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ExperimentListResponse:
    """List experiments with filtering and pagination."""
    service = _get_service(session)
    query = ExperimentQuery(
        project_id=str(current_user.org_id) if current_user.org_id else None,
        status=ExperimentStatus(status) if status else None,
        search=search,
        page=page,
        page_size=page_size,
    )
    result = await service.list_experiments(query)
    return ExperimentListResponse(
        items=[_to_response(e) for e in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
    )


@experiment_router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExperimentResponse:
    """Get an experiment by ID."""
    service = _get_service(session)
    try:
        experiment = await service.get_experiment(UUIDv7.from_string(experiment_id))
        return _to_response(experiment)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@experiment_router.put("/{experiment_id}", response_model=ExperimentResponse)
async def update_experiment(
    experiment_id: str,
    body: UpdateExperimentRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExperimentResponse:
    """Update experiment metadata."""
    service = _get_service(session)
    try:
        experiment = await service.update_experiment(
            UUIDv7.from_string(experiment_id),
            name=body.name,
            description=body.description,
            hypothesis=body.hypothesis,
            conclusion=body.conclusion,
            tags=tuple(body.tags) if body.tags is not None else None,
        )
        await session.commit()
        return _to_response(experiment)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@experiment_router.delete("/{experiment_id}", status_code=204)
async def delete_experiment(
    experiment_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an experiment."""
    service = _get_service(session)
    try:
        await service.delete_experiment(UUIDv7.from_string(experiment_id))
        await session.commit()
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@experiment_router.post("/{experiment_id}/activate", response_model=ExperimentResponse)
async def activate_experiment(
    experiment_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExperimentResponse:
    """Activate a draft experiment."""
    service = _get_service(session)
    try:
        experiment = await service.activate_experiment(UUIDv7.from_string(experiment_id))
        await session.commit()
        return _to_response(experiment)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@experiment_router.post("/{experiment_id}/complete", response_model=ExperimentResponse)
async def complete_experiment(
    experiment_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExperimentResponse:
    """Complete an active experiment."""
    service = _get_service(session)
    try:
        experiment = await service.complete_experiment(UUIDv7.from_string(experiment_id))
        await session.commit()
        return _to_response(experiment)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@experiment_router.post("/{experiment_id}/archive", response_model=ExperimentResponse)
async def archive_experiment(
    experiment_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExperimentResponse:
    """Archive an experiment."""
    service = _get_service(session)
    try:
        experiment = await service.archive_experiment(UUIDv7.from_string(experiment_id))
        await session.commit()
        return _to_response(experiment)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc


@experiment_router.post("/{experiment_id}/baseline", response_model=ExperimentResponse)
async def set_baseline(
    experiment_id: str,
    body: SetBaselineRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExperimentResponse:
    """Set the baseline run for comparison."""
    service = _get_service(session)
    try:
        experiment = await service.set_baseline(UUIDv7.from_string(experiment_id), body.run_id)
        await session.commit()
        return _to_response(experiment)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
