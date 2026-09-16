"""SQLAlchemy repository for durable per-item executions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.execution.item_executor import ItemExecutionResult
from app.infrastructure.database.models.item_execution import ItemExecutionModel


class SqlAlchemyItemExecutionRepository:
    """Stores and retrieves durable provider execution records.

    Instances are cheap and tied to a single session, matching the
    per-activity session pattern used by the evaluation activities.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with a database session."""
        self._session = session

    async def find(self, run_id: str, item_id: str) -> ItemExecutionModel | None:
        """Return the durable execution record for a (run_id, item_id)."""
        row = await self._session.scalar(
            select(ItemExecutionModel).where(
                ItemExecutionModel.run_id == run_id,
                ItemExecutionModel.item_id == item_id,
            )
        )
        return row

    async def upsert(
        self,
        run_id: str,
        item_id: str,
        result: ItemExecutionResult,
    ) -> None:
        """Create or update the durable record for an executed item.

        Converges on the composite primary key: a concurrent retry
        finds the existing row and updates it into a single record
        instead of duplicating it.
        """
        row = await self.find(run_id, item_id)
        if row is None:
            row = ItemExecutionModel(run_id=run_id, item_id=item_id)
            self._session.add(row)
        row.item_index = result.item_index
        row.provider_name = result.provider_name
        row.model_id = result.model_id
        row.prompt = result.prompt
        row.response = result.response
        row.tokens_input = result.tokens_input
        row.tokens_output = result.tokens_output
        row.tokens_cached = result.tokens_cached
        row.cost_usd = result.cost_usd
        row.cost_estimated = result.cost_estimated
        row.latency_ms = result.latency_ms
        row.finish_reason = result.finish_reason
        row.request_id = result.request_id
