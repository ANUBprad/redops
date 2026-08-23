"""SQLAlchemy repository for EvaluationRun persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, overload

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.evaluation.domain.contracts.evaluation_contracts import (
    PaginatedRuns,
    RunQuery,
    RunRepository,
)
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import RunStatus
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    DatasetReference,
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionPolicy,
)
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass


class SqlAlchemyEvaluationRunRepository(RunRepository):
    """SQLAlchemy implementation of the RunRepository contract.

    Maps between the domain EvaluationRun aggregate and the
    EvaluationRunModel ORM representation.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with an async database session."""
        self._session = session

    async def save(self, run: EvaluationRun) -> None:
        """Persist an evaluation run (create or update).

        Args:
            run: The evaluation run aggregate to persist.

        Raises:
            ConflictError: If a unique constraint is violated.

        """
        model = self._to_model(run)
        await self._session.merge(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                message=f"Evaluation run {run.id} failed to persist",
                details={"run_id": str(run.id)},
            ) from exc

    async def find_by_id(self, run_id: UUIDv7) -> EvaluationRun | None:
        """Find a run by its ID.

        Args:
            run_id: The UUIDv7 identifier.

        Returns:
            The EvaluationRun aggregate if found, None otherwise.

        """
        stmt = select(EvaluationRunModel).where(
            EvaluationRunModel.id == str(run_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_status(
        self,
        status: RunStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvaluationRun]:
        """Find runs by status with pagination.

        Args:
            status: The run status to filter by.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of matching EvaluationRun aggregates.

        """
        stmt = (
            select(EvaluationRunModel)
            .where(EvaluationRunModel.status == status.value)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        return [self._to_domain(m) for m in models]

    async def list(self, query: RunQuery) -> PaginatedRuns:
        """List runs with filtering, sorting, and pagination.

        Args:
            query: Query parameters for filtering and pagination.

        Returns:
            Paginated list of evaluation runs.

        """
        stmt = select(EvaluationRunModel)
        count_stmt = select(func.count()).select_from(EvaluationRunModel)

        if query.evaluation_id is not None:
            stmt = stmt.where(
                EvaluationRunModel.evaluation_id == query.evaluation_id,
            )
            count_stmt = count_stmt.where(
                EvaluationRunModel.evaluation_id == query.evaluation_id,
            )
        if query.status is not None:
            stmt = stmt.where(EvaluationRunModel.status == query.status.value)
            count_stmt = count_stmt.where(
                EvaluationRunModel.status == query.status.value,
            )
        if query.provider is not None:
            stmt = stmt.where(EvaluationRunModel.provider == query.provider)
            count_stmt = count_stmt.where(
                EvaluationRunModel.provider == query.provider,
            )
        if query.model is not None:
            stmt = stmt.where(EvaluationRunModel.model == query.model)
            count_stmt = count_stmt.where(
                EvaluationRunModel.model == query.model,
            )
        if query.search is not None:
            search_pattern = f"%{query.search}%"
            search_filter = EvaluationRunModel.evaluation_name.ilike(
                search_pattern,
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        sort_column = _get_sort_column(query.sort_by)
        if query.sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        return PaginatedRuns(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def exists(self, run_id: UUIDv7) -> bool:
        """Check whether a run exists.

        Args:
            run_id: The UUIDv7 identifier.

        Returns:
            True if the run exists, False otherwise.

        """
        stmt = select(EvaluationRunModel.id).where(
            EvaluationRunModel.id == str(run_id),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def delete(self, run_id: UUIDv7) -> bool:
        """Delete a run by ID.

        Args:
            run_id: The UUIDv7 identifier.

        Returns:
            True if deleted, False if not found.

        """
        stmt = select(EvaluationRunModel).where(
            EvaluationRunModel.id == str(run_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    async def persist_progress(self, run: EvaluationRun) -> None:
        """Persist progress-only updates (counters, tokens, cost).

        Args:
            run: The run with updated progress fields.

        """
        model = self._to_model(run)
        await self._session.merge(model)

    async def find_by_date_range(
        self,
        since: datetime,
        until: datetime,
        provider: str | None = None,
        model: str | None = None,
    ) -> Sequence[EvaluationRun]:
        """Find runs created within a date range, optionally filtered."""
        stmt = select(EvaluationRunModel).where(
            EvaluationRunModel.created_at >= since,
            EvaluationRunModel.created_at <= until,
        )
        if provider is not None:
            stmt = stmt.where(EvaluationRunModel.provider == provider)
        if model is not None:
            stmt = stmt.where(EvaluationRunModel.model == model)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    @staticmethod
    def _to_model(run: EvaluationRun) -> EvaluationRunModel:
        """Convert a domain EvaluationRun to an ORM model.

        Args:
            run: The domain aggregate.

        Returns:
            The corresponding ORM model.

        """
        return EvaluationRunModel(
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
            token_input=run.token_input,
            token_output=run.token_output,
            cost=run.cost,
            average_latency_ms=run.average_latency_ms,
            failure_reason=(
                run.failure_summary.first_failure if run.failure_summary is not None else None
            ),
            config=_serialize_config(run.config),
            profile=_serialize_profile(run.profile),
            metadata_=_serialize_metadata(run.metadata),
            started_at=run.started_at,
            completed_at=run.completed_at,
            cancelled_at=run.cancelled_at,
            version=run.version,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _to_domain(model: EvaluationRunModel) -> EvaluationRun:
        """Convert an ORM model to a domain EvaluationRun.

        Args:
            model: The ORM model.

        Returns:
            The corresponding domain aggregate.

        """
        config = _deserialize_config(model.config)
        profile = _deserialize_profile(model.profile)
        metadata = _deserialize_metadata(model.metadata_)

        run = EvaluationRun(
            evaluation_name=model.evaluation_name,
            config=config,
            profile=profile,
            metadata=metadata,
            entity_id=UUIDv7.from_string(model.id),
            evaluation_id=model.evaluation_id,
            workflow_id=model.workflow_id,
        )
        run._status = RunStatus(model.status)
        run.items_total = model.items_total
        run.items_completed = model.items_completed
        run.items_failed = model.items_failed
        run.token_input = model.token_input
        run.token_output = model.token_output
        run.cost = model.cost
        run.average_latency_ms = model.average_latency_ms
        run.started_at = _as_utc(model.started_at)
        run.completed_at = _as_utc(model.completed_at)
        run.cancelled_at = _as_utc(model.cancelled_at)
        run.version = model.version
        run.created_at = _as_utc(model.created_at)
        run.updated_at = _as_utc(model.updated_at)
        return run


@overload
def _as_utc(value: datetime) -> datetime: ...


@overload
def _as_utc(value: datetime | None) -> datetime | None: ...


def _as_utc(value: datetime | None) -> datetime | None:
    """Normalize a stored datetime to timezone-aware UTC.

    SQLite drops tzinfo on persistence; rehydrated timestamps must be
    UTC-aware so domain arithmetic (e.g. duration) cannot mix naive and
    aware datetimes.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _get_sort_column(sort_by: str) -> Any:
    """Map a sort field name to the corresponding ORM column.

    Args:
        sort_by: The field name to sort by.

    Returns:
        The corresponding SQLAlchemy column.

    """
    columns: dict[str, Any] = {
        "created_at": EvaluationRunModel.created_at,
        "updated_at": EvaluationRunModel.updated_at,
        "started_at": EvaluationRunModel.started_at,
        "evaluation_name": EvaluationRunModel.evaluation_name,
    }
    return columns.get(sort_by, EvaluationRunModel.created_at)


def _serialize_config(config: EvaluationConfiguration) -> dict[str, Any]:
    """Serialize an EvaluationConfiguration to a JSON-compatible dict."""
    return {
        "name": config.name,
        "eval_type": config.eval_type.value,
        "profile": _serialize_profile(config.profile),
        "dataset": (
            {"dataset_id": config.dataset.dataset_id, "row_count": config.dataset.row_count}
            if config.dataset is not None
            else None
        ),
        "metrics": list(config.metrics),
        "budget": {
            "max_cost_usd": config.budget.max_cost_usd,
            "max_tokens": config.budget.max_tokens,
            "max_duration_seconds": config.budget.max_duration_seconds,
        },
        "limits": {
            "max_concurrency": config.limits.max_concurrency,
            "batch_size": config.limits.batch_size,
            "checkpoint_interval": config.limits.checkpoint_interval,
        },
        "policy": {
            "continue_on_item_failure": config.policy.continue_on_item_failure,
            "max_retries_per_item": config.policy.max_retries_per_item,
            "timeout_per_item_seconds": config.policy.timeout_per_item_seconds,
        },
        "priority": config.priority.value,
    }


def _serialize_profile(profile: EvaluationProfile) -> dict[str, Any]:
    """Serialize an EvaluationProfile to a JSON-compatible dict."""
    return {
        "provider_name": profile.provider_name,
        "model_id": profile.model_id,
        "temperature": profile.temperature,
        "max_tokens": profile.max_tokens,
        "timeout_seconds": profile.timeout_seconds,
        "system_prompt": profile.system_prompt,
    }


def _serialize_metadata(metadata: EvaluationMetadata) -> dict[str, Any]:
    """Serialize EvaluationMetadata to a JSON-compatible dict."""
    return {
        "project_id": metadata.project_id,
        "created_by": metadata.created_by,
        "tags": list(metadata.tags),
        "description": metadata.description,
    }


def _deserialize_config(data: dict[str, Any]) -> EvaluationConfiguration:
    """Deserialize a dict to EvaluationConfiguration."""
    profile_data = data.get("profile", {})
    dataset_data = data.get("dataset")
    budget_data = data.get("budget", {})
    limits_data = data.get("limits", {})
    policy_data = data.get("policy", {})

    from app.evaluation.domain.enums.evaluation_enums import EvaluationType, Priority

    return EvaluationConfiguration(
        name=data.get("name", ""),
        eval_type=EvaluationType(data.get("eval_type", "single")),
        profile=EvaluationProfile(
            provider_name=profile_data.get("provider_name", ""),
            model_id=profile_data.get("model_id", ""),
            temperature=profile_data.get("temperature", 0.0),
            max_tokens=profile_data.get("max_tokens", 4096),
            timeout_seconds=profile_data.get("timeout_seconds", 60),
            system_prompt=profile_data.get("system_prompt"),
        ),
        dataset=(
            DatasetReference(
                dataset_id=dataset_data["dataset_id"],
                row_count=dataset_data.get("row_count", 0),
            )
            if dataset_data is not None
            else None
        ),
        metrics=tuple(data.get("metrics", ())),
        budget=ExecutionBudget(
            max_cost_usd=budget_data.get("max_cost_usd"),
            max_tokens=budget_data.get("max_tokens"),
            max_duration_seconds=budget_data.get("max_duration_seconds"),
        ),
        limits=ExecutionLimits(
            max_concurrency=limits_data.get("max_concurrency", 1),
            batch_size=limits_data.get("batch_size", 50),
            checkpoint_interval=limits_data.get("checkpoint_interval", 50),
        ),
        policy=ExecutionPolicy(
            continue_on_item_failure=policy_data.get("continue_on_item_failure", True),
            max_retries_per_item=policy_data.get("max_retries_per_item", 0),
            timeout_per_item_seconds=policy_data.get("timeout_per_item_seconds"),
        ),
        priority=Priority(data.get("priority", "normal")),
    )


def _deserialize_profile(data: dict[str, Any]) -> EvaluationProfile:
    """Deserialize a dict to EvaluationProfile."""
    return EvaluationProfile(
        provider_name=data.get("provider_name", ""),
        model_id=data.get("model_id", ""),
        temperature=data.get("temperature", 0.0),
        max_tokens=data.get("max_tokens", 4096),
        timeout_seconds=data.get("timeout_seconds", 60),
        system_prompt=data.get("system_prompt"),
    )


def _deserialize_metadata(data: dict[str, Any]) -> EvaluationMetadata:
    """Deserialize a dict to EvaluationMetadata."""
    return EvaluationMetadata(
        project_id=data.get("project_id"),
        created_by=data.get("created_by"),
        tags=tuple(data.get("tags", ())),
        description=data.get("description"),
    )
