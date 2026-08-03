"""SQLAlchemy repository for AgentRun persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.agents.domain.contracts.agent_contracts import (
    AgentRunQuery,
    AgentRunRepository,
    PaginatedAgentRuns,
)
from app.agents.domain.entities.agent_entities import AgentRun
from app.agents.domain.enums.agent_enums import AgentRunStatus
from app.agents.domain.value_objects.agent_value_objects import (
    AgentConfiguration,
    AgentProfile,
    AgentRunMetadata,
)
from app.infrastructure.database.models.agent_run import AgentRunModel
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass


class SqlAlchemyAgentRunRepository(AgentRunRepository):
    """SQLAlchemy implementation of the AgentRunRepository contract."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, run: AgentRun) -> None:
        model = self._to_model(run)
        await self._session.merge(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                message=f"Agent run {run.id} failed to persist",
                details={"run_id": str(run.id)},
            ) from exc

    async def find_by_id(self, run_id: UUIDv7) -> AgentRun | None:
        stmt = select(AgentRunModel).where(
            AgentRunModel.id == str(run_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_status(
        self,
        status: AgentRunStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentRun]:
        stmt = (
            select(AgentRunModel)
            .where(AgentRunModel.status == status.value)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        return [self._to_domain(m) for m in models]

    async def list(self, query: AgentRunQuery) -> PaginatedAgentRuns:
        stmt = select(AgentRunModel)
        count_stmt = select(func.count()).select_from(AgentRunModel)

        if query.agent_name is not None:
            stmt = stmt.where(AgentRunModel.agent_name == query.agent_name)
            count_stmt = count_stmt.where(
                AgentRunModel.agent_name == query.agent_name,
            )
        if query.status is not None:
            stmt = stmt.where(AgentRunModel.status == query.status.value)
            count_stmt = count_stmt.where(
                AgentRunModel.status == query.status.value,
            )
        if query.provider is not None:
            stmt = stmt.where(AgentRunModel.provider == query.provider)
            count_stmt = count_stmt.where(
                AgentRunModel.provider == query.provider,
            )
        if query.model is not None:
            stmt = stmt.where(AgentRunModel.model == query.model)
            count_stmt = count_stmt.where(
                AgentRunModel.model == query.model,
            )
        if query.search is not None:
            search_pattern = f"%{query.search}%"
            search_filter = AgentRunModel.agent_name.ilike(search_pattern)
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

        return PaginatedAgentRuns(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def exists(self, run_id: UUIDv7) -> bool:
        stmt = select(AgentRunModel.id).where(
            AgentRunModel.id == str(run_id),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def delete(self, run_id: UUIDv7) -> bool:
        stmt = select(AgentRunModel).where(
            AgentRunModel.id == str(run_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    async def persist_progress(self, run: AgentRun) -> None:
        model = self._to_model(run)
        await self._session.merge(model)

    @staticmethod
    def _to_model(run: AgentRun) -> AgentRunModel:
        return AgentRunModel(
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
            token_input=run.token_input,
            token_output=run.token_output,
            cost=run.cost,
            average_latency_ms=run.average_latency_ms,
            failure_reason=(run.failure_summary.value if run.failure_summary is not None else None),
            config=_serialize_config(run.config),
            metadata_=_serialize_metadata(run.metadata),
            started_at=run.started_at,
            completed_at=run.completed_at,
            cancelled_at=run.cancelled_at,
            version=run.version,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _to_domain(model: AgentRunModel) -> AgentRun:
        config = _deserialize_config(model.config)
        metadata = _deserialize_metadata(model.metadata_)

        run = AgentRun(
            agent_name=model.agent_name,
            config=config,
            metadata=metadata,
            entity_id=UUIDv7.from_string(model.id),
            agent_definition_id=model.agent_definition_id,
            workflow_id=model.workflow_id,
        )
        run._status = AgentRunStatus(model.status)
        run.steps_total = model.steps_total
        run.steps_completed = model.steps_completed
        run.steps_failed = model.steps_failed
        run.token_input = model.token_input
        run.token_output = model.token_output
        run.cost = model.cost
        run.average_latency_ms = model.average_latency_ms
        run.started_at = model.started_at
        run.completed_at = model.completed_at
        run.cancelled_at = model.cancelled_at
        run.version = model.version
        run.created_at = model.created_at
        run.updated_at = model.updated_at
        return run


def _get_sort_column(sort_by: str) -> Any:
    columns: dict[str, Any] = {
        "created_at": AgentRunModel.created_at,
        "updated_at": AgentRunModel.updated_at,
        "started_at": AgentRunModel.started_at,
        "agent_name": AgentRunModel.agent_name,
    }
    return columns.get(sort_by, AgentRunModel.created_at)


def _serialize_config(config: AgentConfiguration) -> dict[str, Any]:
    return {
        "name": config.name,
        "profile": {
            "provider_name": config.profile.provider_name,
            "model_id": config.profile.model_id,
            "temperature": config.profile.temperature,
            "max_tokens": config.profile.max_tokens,
            "timeout_seconds": config.profile.timeout_seconds,
            "system_prompt": config.profile.system_prompt,
        },
        "tools": list(config.tools),
        "max_steps": config.max_steps,
        "max_retries": config.max_retries,
        "timeout_seconds": config.timeout_seconds,
        "checkpoint_interval": config.checkpoint_interval,
    }


def _serialize_metadata(metadata: AgentRunMetadata) -> dict[str, Any]:
    return {
        "project_id": metadata.project_id,
        "created_by": metadata.created_by,
        "tags": list(metadata.tags),
        "description": metadata.description,
    }


def _deserialize_config(data: dict[str, Any]) -> AgentConfiguration:
    profile_data = data.get("profile", {})
    return AgentConfiguration(
        name=data.get("name", ""),
        profile=AgentProfile(
            provider_name=profile_data.get("provider_name", ""),
            model_id=profile_data.get("model_id", ""),
            temperature=profile_data.get("temperature", 0.0),
            max_tokens=profile_data.get("max_tokens", 4096),
            timeout_seconds=profile_data.get("timeout_seconds", 120),
            system_prompt=profile_data.get("system_prompt"),
        ),
        tools=tuple(data.get("tools", [])),
        max_steps=data.get("max_steps", 10),
        max_retries=data.get("max_retries", 3),
        timeout_seconds=data.get("timeout_seconds", 300),
        checkpoint_interval=data.get("checkpoint_interval", 5),
    )


def _deserialize_metadata(data: dict[str, Any]) -> AgentRunMetadata:
    return AgentRunMetadata(
        project_id=data.get("project_id"),
        created_by=data.get("created_by"),
        tags=tuple(data.get("tags", [])),
        description=data.get("description"),
    )
