"""SQLAlchemy repository for AgentTrajectory persistence."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.agents.domain.contracts.agent_contracts import (
    AgentTrajectoryRepository,
    PaginatedTrajectories,
    TrajectoryQuery,
)
from app.infrastructure.database.models.agent_trajectory import AgentTrajectoryModel

try:
    from sqlalchemy.ext.asyncio import AsyncSession
except ImportError:  # pragma: no cover
    pass


class SqlAlchemyAgentTrajectoryRepository(AgentTrajectoryRepository):
    """SQLAlchemy implementation of AgentTrajectoryRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, trajectory: dict[str, object]) -> None:
        model = AgentTrajectoryModel(
            id=str(trajectory.get("trajectory_id", "")),
            run_id=str(trajectory.get("run_id", "")),
            agent_name=str(trajectory.get("agent_name", "")),
            status=str(trajectory.get("status", "")),
            total_steps=_to_int(trajectory.get("total_steps")),
            total_llm_calls=_to_int(trajectory.get("total_llm_calls")),
            total_tool_calls=_to_int(trajectory.get("total_tool_calls")),
            total_tokens_input=_to_int(trajectory.get("total_tokens_input")),
            total_tokens_output=_to_int(trajectory.get("total_tokens_output")),
            total_cost_usd=_to_float(trajectory.get("total_cost_usd")),
            total_duration_ms=_to_int(trajectory.get("total_duration_ms")),
            final_response=str(trajectory.get("final_response", "")),
            conversation_history=_to_dict(trajectory.get("conversation_history")),
            tool_calls=_to_dict(trajectory.get("tool_calls")),
            llm_calls=_to_dict(trajectory.get("llm_calls")),
            error=trajectory.get("error") if isinstance(trajectory.get("error"), str) else None,
            metadata_=_to_dict(trajectory.get("metadata")),
        )
        await self._session.merge(model)
        await self._session.flush()

    async def find_by_id(self, trajectory_id: str) -> dict[str, object] | None:
        stmt = select(AgentTrajectoryModel).where(
            AgentTrajectoryModel.id == trajectory_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_dict(model)

    async def find_by_run_id(self, run_id: str) -> dict[str, object] | None:
        stmt = select(AgentTrajectoryModel).where(
            AgentTrajectoryModel.run_id == run_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_dict(model)

    async def list(self, query: TrajectoryQuery) -> PaginatedTrajectories:
        stmt = select(AgentTrajectoryModel)
        count_stmt = select(func.count()).select_from(AgentTrajectoryModel)

        if query.run_id is not None:
            stmt = stmt.where(AgentTrajectoryModel.run_id == query.run_id)
            count_stmt = count_stmt.where(AgentTrajectoryModel.run_id == query.run_id)
        if query.agent_name is not None:
            stmt = stmt.where(AgentTrajectoryModel.agent_name == query.agent_name)
            count_stmt = count_stmt.where(AgentTrajectoryModel.agent_name == query.agent_name)
        if query.status is not None:
            stmt = stmt.where(AgentTrajectoryModel.status == query.status)
            count_stmt = count_stmt.where(AgentTrajectoryModel.status == query.status)

        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        if query.sort_order == "desc":
            stmt = stmt.order_by(AgentTrajectoryModel.created_at.desc())
        else:
            stmt = stmt.order_by(AgentTrajectoryModel.created_at.asc())

        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)

        result = await self._session.execute(stmt)
        models = list(result.scalars().all())

        return PaginatedTrajectories(
            items=[self._to_dict(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def delete(self, trajectory_id: str) -> bool:
        stmt = select(AgentTrajectoryModel).where(
            AgentTrajectoryModel.id == trajectory_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        return True

    @staticmethod
    def _to_dict(model: AgentTrajectoryModel) -> dict[str, Any]:
        return {
            "trajectory_id": model.id,
            "run_id": model.run_id,
            "agent_name": model.agent_name,
            "status": model.status,
            "total_steps": model.total_steps,
            "total_llm_calls": model.total_llm_calls,
            "total_tool_calls": model.total_tool_calls,
            "total_tokens_input": model.total_tokens_input,
            "total_tokens_output": model.total_tokens_output,
            "total_cost_usd": model.total_cost_usd,
            "total_duration_ms": model.total_duration_ms,
            "final_response": model.final_response,
            "conversation_history": model.conversation_history,
            "tool_calls": model.tool_calls,
            "llm_calls": model.llm_calls,
            "error": model.error,
            "metadata": model.metadata_,
            "created_at": model.created_at.isoformat() if model.created_at else "",
            "updated_at": model.updated_at.isoformat() if model.updated_at else "",
        }


def _to_int(value: object, default: int = 0) -> int:
    """Safely convert a value to int."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _to_float(value: object, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _to_dict(value: object) -> dict[str, object]:
    """Safely convert a value to dict."""
    if isinstance(value, dict):
        return value
    return {}
