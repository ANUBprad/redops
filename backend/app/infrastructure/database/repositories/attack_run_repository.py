"""SQLAlchemy repository for Attack Runs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models.attack_run import AttackRunModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError
from app.redteam.contracts.repositories import (
    AttackRunQuery,
    AttackRunRepository,
    PaginatedAttackRuns,
)
from app.redteam.domain.entities import AttackRun
from app.redteam.domain.enums import AttackCategory, AttackSeverity, AttackStatus
from app.redteam.domain.value_objects import AttackConfiguration, AttackMutation

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_SORT_MAP: dict[str, str] = {
    "status": "status",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "started_at": "started_at",
    "completed_at": "completed_at",
}


def _get_sort_column(sort_by: str) -> str:
    return _SORT_MAP.get(sort_by, "created_at")


class SqlAlchemyAttackRunRepository(AttackRunRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, run: AttackRun) -> None:
        model = self._to_model(run)
        try:
            await self._session.merge(model)
        except IntegrityError as exc:
            raise ConflictError(f"Attack run {run.id} conflicts") from exc

    async def find_by_id(self, run_id: UUIDv7) -> AttackRun | None:
        stmt = select(AttackRunModel).where(AttackRunModel.id == str(run_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list(self, query: AttackRunQuery) -> PaginatedAttackRuns:
        stmt = select(AttackRunModel)

        if query.status:
            stmt = stmt.where(AttackRunModel.status == query.status.value)
        if query.evaluation_run_id:
            stmt = stmt.where(AttackRunModel.evaluation_run_id == query.evaluation_run_id)
        if query.category:
            stmt = stmt.where(
                AttackRunModel.configuration["categories"]
                .as_string()
                .contains(query.category.value)
            )

        sort_col = _get_sort_column(query.sort_by)
        sort_attr = getattr(AttackRunModel, sort_col, AttackRunModel.created_at)
        order = sort_attr.desc() if query.sort_order == "desc" else sort_attr.asc()
        stmt = stmt.order_by(order)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return PaginatedAttackRuns(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def exists(self, run_id: UUIDv7) -> bool:
        stmt = select(AttackRunModel).where(AttackRunModel.id == str(run_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def persist_progress(self, run: AttackRun) -> None:
        stmt = select(AttackRunModel).where(AttackRunModel.id == str(run.id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return
        model.status = run.status.value
        model.items_completed = run.items_completed
        model.items_passed = run.items_passed
        model.items_violated = run.items_violated
        model.items_failed = run.items_failed
        model.version = run.version
        model.started_at = run.started_at
        model.completed_at = run.completed_at

    async def persist_campaign_results(
        self,
        run_id: UUIDv7,
        campaign_results: dict[str, Any],
    ) -> None:
        """Persist campaign results JSON to the attack run."""
        stmt = select(AttackRunModel).where(AttackRunModel.id == str(run_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return
        model.campaign_results = campaign_results
        model.updated_at = datetime.now(UTC)

    async def find_by_date_range(
        self,
        since: datetime,
        until: datetime,
    ) -> Sequence[AttackRun]:
        """Find attack runs created within a date range."""
        stmt = select(AttackRunModel).where(
            AttackRunModel.created_at >= since,
            AttackRunModel.created_at <= until,
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    @staticmethod
    def _to_model(run: AttackRun) -> AttackRunModel:
        return AttackRunModel(
            id=str(run.id),
            evaluation_run_id=str(run.evaluation_run_id) if run.evaluation_run_id else None,
            status=run.status.value,
            attack_definition_ids=[str(did) for did in run.attack_definition_ids],
            configuration=_config_to_dict(run.configuration),
            items_total=run.items_total,
            items_completed=run.items_completed,
            items_passed=run.items_passed,
            items_violated=run.items_violated,
            items_failed=run.items_failed,
            version=run.version,
            campaign_results=run.campaign_results,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _to_domain(model: AttackRunModel) -> AttackRun:
        return AttackRun(
            entity_id=UUIDv7(UUID(model.id)),
            evaluation_run_id=UUIDv7(UUID(model.evaluation_run_id))
            if model.evaluation_run_id
            else None,
            attack_definition_ids=tuple(
                UUIDv7(UUID(did)) for did in (model.attack_definition_ids or [])
            ),
            configuration=_dict_to_config(model.configuration or {}),
            status=AttackStatus(model.status),
            items_total=model.items_total,
            items_completed=model.items_completed,
            items_passed=model.items_passed,
            items_violated=model.items_violated,
            items_failed=model.items_failed,
            campaign_results=model.campaign_results,
        )


def _config_to_dict(config: AttackConfiguration | None) -> dict[str, Any]:
    if config is None:
        return {}
    return {
        "target_provider": config.target_provider,
        "target_model": config.target_model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "timeout_seconds": config.timeout_seconds,
        "system_prompt": config.system_prompt,
        "attack_definitions": [str(aid) for aid in config.attack_definitions],
        "categories": [c.value for c in config.categories],
        "severities": [s.value for s in config.severities],
        "max_scenarios": config.max_scenarios,
        "mutations": [_mutation_to_dict(m) for m in config.mutations],
        "continue_on_violation": config.continue_on_violation,
        "metadata": config.metadata,
    }


def _dict_to_config(data: dict[str, Any]) -> AttackConfiguration:
    return AttackConfiguration(
        target_provider=data.get("target_provider", ""),
        target_model=data.get("target_model", ""),
        temperature=data.get("temperature", 0.0),
        max_tokens=data.get("max_tokens", 2048),
        timeout_seconds=data.get("timeout_seconds", 60),
        system_prompt=data.get("system_prompt", ""),
        attack_definitions=tuple(UUIDv7(UUID(aid)) for aid in data.get("attack_definitions", [])),
        categories=tuple(AttackCategory(c) for c in data.get("categories", [])),
        severities=tuple(AttackSeverity(s) for s in data.get("severities", [])),
        max_scenarios=data.get("max_scenarios", 0),
        mutations=tuple(_dict_to_mutation(m) for m in data.get("mutations", [])),
        continue_on_violation=data.get("continue_on_violation", True),
        metadata=dict(data.get("metadata", {})),
    )


def _mutation_to_dict(mutation: AttackMutation) -> dict[str, Any]:
    return {
        "mutation_id": str(mutation.mutation_id),
        "name": mutation.name,
        "description": mutation.description,
        "transform": mutation.transform,
        "parameters": mutation.parameters,
    }


def _dict_to_mutation(data: dict[str, Any]) -> AttackMutation:
    return AttackMutation(
        mutation_id=data.get("mutation_id", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        transform=data.get("transform", ""),
        parameters=dict(data.get("parameters", {})),
    )
