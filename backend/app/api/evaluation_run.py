"""REST endpoints for evaluation run management."""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient

from app.core.config import AppConfig
from app.core.dependencies import (
    CurrentUser,
    get_config_dependency,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.evaluation.application.run_commands import (
    CancelEvaluationRunCommand,
    CreateEvaluationRunCommand,
    GetEvaluationRunQuery,
    ListEvaluationRunsQuery,
    QueueEvaluationRunCommand,
    RetryEvaluationRunCommand,
)
from app.evaluation.application.run_handlers import (
    CancelEvaluationRunHandler,
    CreateEvaluationRunHandler,
    GetEvaluationRunHandler,
    ListEvaluationRunsHandler,
    QueueEvaluationRunHandler,
    RetryEvaluationRunHandler,
)
from app.evaluation.temporal.workflow import EvaluationRunWorkflow, EvaluationRunWorkflowInput
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)
from app.kernel.exceptions.errors import BaseError
from app.schemas.evaluation_run import (
    CancelRunRequest,
    CreateEvaluationRunRequest,
    DatasetItemRequest,
    RunListResponse,
    RunResponse,
    RunSummaryResponse,
)

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import PaginatedRuns
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

run_router = APIRouter(prefix="/runs", tags=["runs"])


def _idempotent_workflow_id(idempotency_key: str) -> str:
    """Derive a deterministic Temporal workflow ID from an idempotency key.

    The key is hashed so that arbitrary caller-supplied values map to a
    stable, namespaced workflow ID without risking duplicate runs on retry.

    Args:
        idempotency_key: The caller-supplied idempotency key.

    Returns:
        A deterministic workflow ID derived from the key.

    """
    digest = sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
    return f"evaluation-run-idem-{digest}"


def _get_repository(session: AsyncSession) -> SqlAlchemyEvaluationRunRepository:
    """Create a repository from the database session."""
    return SqlAlchemyEvaluationRunRepository(session)


def _item_to_payload(item: DatasetItemRequest) -> dict[str, str]:
    """Convert an API dataset item to a workflow payload.

    Args:
        item: The API dataset item.

    Returns:
        A string-keyed payload with only the populated fields.

    """
    payload: dict[str, str] = {"prompt": item.prompt}
    if item.reference is not None:
        payload["reference"] = item.reference
    if item.context is not None:
        payload["context"] = item.context
    if item.id is not None:
        payload["item_id"] = item.id
    return payload


def _run_to_response(run: EvaluationRun) -> RunResponse:
    """Convert a domain EvaluationRun to an API response."""
    return RunResponse(
        id=str(run.id),
        evaluation_id=run.evaluation_id,
        evaluation_name=run.evaluation_name,
        workflow_id=run.workflow_id,
        provider=run.profile.provider_name,
        model=run.profile.model_id,
        status=run.status.value,
        priority=run.priority.value,
        items_total=run.items_total,
        items_completed=run.items_completed,
        items_failed=run.items_failed,
        progress=run.progress,
        token_input=run.token_input,
        token_output=run.token_output,
        total_tokens=run.total_tokens,
        cost=run.cost,
        average_latency_ms=run.average_latency_ms,
        failure_reason=(
            run.failure_summary.first_failure if run.failure_summary is not None else None
        ),
        verdict=run.verdict,
        version=run.version,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        cancelled_at=run.cancelled_at.isoformat() if run.cancelled_at else None,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


def _run_to_summary(run: EvaluationRun) -> RunSummaryResponse:
    """Convert a domain EvaluationRun to a summary response."""
    return RunSummaryResponse(
        id=str(run.id),
        evaluation_id=run.evaluation_id,
        evaluation_name=run.evaluation_name,
        provider=run.profile.provider_name,
        model=run.profile.model_id,
        status=run.status.value,
        progress=run.progress,
        items_total=run.items_total,
        items_completed=run.items_completed,
        items_failed=run.items_failed,
        cost=run.cost,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        created_at=run.created_at.isoformat(),
    )


def _to_list_response(paginated: PaginatedRuns) -> RunListResponse:
    """Convert paginated runs to list response."""
    return RunListResponse(
        items=[_run_to_summary(i) for i in paginated.items],
        total=paginated.total,
        page=paginated.page,
        page_size=paginated.page_size,
        total_pages=paginated.total_pages,
    )


@run_router.post("", response_model=RunResponse, status_code=201)
async def create_run(
    body: CreateEvaluationRunRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    temporal_client: TemporalClient = Depends(get_temporal_client),
    config: AppConfig = Depends(get_config_dependency),
) -> RunResponse:
    """Create a new evaluation run and schedule its execution.

    The endpoint is idempotent when an ``Idempotency-Key`` header is
    supplied: a repeated key returns the previously created run instead of
    scheduling a duplicate, enabling safe CI/CD retries.
    """
    repo = _get_repository(session)

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        existing = await repo.find_by_workflow_id(_idempotent_workflow_id(idempotency_key))
        if existing is not None:
            return _run_to_response(existing)

    handler = CreateEvaluationRunHandler(repo)
    command = CreateEvaluationRunCommand(
        evaluation_id=body.evaluation_id,
        evaluation_name=body.evaluation_name,
        provider=body.provider,
        model=body.model,
        metrics=tuple(body.metrics),
        project_id=body.project_id,
        created_by=current_user.user_id,
        tags=tuple(body.tags),
        workflow_id=body.workflow_id,
        system_prompt=body.system_prompt,
        prompt_template=body.prompt_template,
        dataset_items=tuple(_item_to_payload(item) for item in body.dataset_items),
    )
    try:
        run = await handler.handle(command)
        await session.flush()

        dataset_items = tuple(_item_to_payload(item) for item in body.dataset_items)
        total_items = body.total_items or len(dataset_items)

        workflow_id = (
            _idempotent_workflow_id(idempotency_key)
            if idempotency_key
            else f"evaluation-run-{run.id}"
        )
        await temporal_client.start_workflow(
            EvaluationRunWorkflow.run,
            EvaluationRunWorkflowInput(
                run_id=str(run.id),
                total_items=total_items,
                provider_name=body.provider,
                model_id=body.model,
                metric_names=tuple(body.metrics),
                dataset_items=dataset_items,
                prompt_template=body.prompt_template,
                system_prompt=body.system_prompt,
            ),
            id=workflow_id,
            task_queue=config.temporal_task_queue,
            execution_timeout=timedelta(hours=24),
        )

        queue_handler = QueueEvaluationRunHandler(repo)
        queue_command = QueueEvaluationRunCommand(run_id=str(run.id))
        run = await queue_handler.handle(queue_command)
        run.workflow_id = workflow_id
        await repo.save(run)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@run_router.get("", response_model=RunListResponse)
async def list_runs(
    evaluation_id: str | None = Query(default=None),
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
) -> RunListResponse:
    """List evaluation runs with filtering, sorting, and pagination."""
    repo = _get_repository(session)
    handler = ListEvaluationRunsHandler(repo)
    query = ListEvaluationRunsQuery(
        evaluation_id=evaluation_id,
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


@run_router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    """Get an evaluation run by ID."""
    repo = _get_repository(session)
    handler = GetEvaluationRunHandler(repo)
    query = GetEvaluationRunQuery(run_id=run_id)
    try:
        run = await handler.handle(query)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@run_router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(
    run_id: str,
    body: CancelRunRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    temporal_client: TemporalClient = Depends(get_temporal_client),
) -> RunResponse:
    """Cancel an evaluation run."""
    repo = _get_repository(session)
    handler = CancelEvaluationRunHandler(repo)
    command = CancelEvaluationRunCommand(
        run_id=run_id,
        reason=body.reason,
        force=body.force,
    )
    try:
        run = await handler.handle(command)
        if run.workflow_id:
            try:
                handle = temporal_client.get_workflow_handle(run.workflow_id)
                await handle.signal(EvaluationRunWorkflow.cancel)
            except Exception:
                pass
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@run_router.post("/{run_id}/retry", response_model=RunResponse, status_code=201)
async def retry_run(
    run_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    """Retry a failed evaluation run."""
    repo = _get_repository(session)
    handler = RetryEvaluationRunHandler(repo)
    command = RetryEvaluationRunCommand(run_id=run_id)
    try:
        run = await handler.handle(command)
    except BaseError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    return _run_to_response(run)


@run_router.get(
    "/evaluation/{evaluation_id}",
    response_model=RunListResponse,
)
async def list_runs_for_evaluation(
    evaluation_id: str,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RunListResponse:
    """List all runs for a specific evaluation definition."""
    repo = _get_repository(session)
    handler = ListEvaluationRunsHandler(repo)
    query = ListEvaluationRunsQuery(
        evaluation_id=evaluation_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    result = await handler.handle(query)
    return _to_list_response(result)
