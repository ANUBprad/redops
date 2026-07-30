"""SQLAlchemy repository for metric result persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.domain.contracts.evaluation_contracts import (
    MetricResultQuery,
    MetricResultRepository,
    PaginatedMetricResults,
)
from app.evaluation.metrics.domain import MetricAggregation, MetricResult
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from collections.abc import Sequence


class SqlAlchemyMetricResultRepository(MetricResultRepository):
    """SQLAlchemy implementation of MetricResultRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with a database session."""
        self._session = session

    @staticmethod
    def _to_domain(model: MetricResultModel) -> MetricResult:
        """Convert an ORM model to a domain MetricResult."""
        return MetricResult(
            metric_name=model.metric_name,
            score=model.score,
            normalized_score=model.normalized_score,
            raw_output=model.raw_output or "",
            reasoning=model.reasoning or "",
            metadata=model.metadata_json or {},
            execution_time_ms=model.execution_time_ms,
            error=model.error,
        )

    @staticmethod
    def _to_model(result: MetricResult, run_id: str, item_id: str) -> MetricResultModel:
        """Convert a domain MetricResult to an ORM model."""
        return MetricResultModel(
            run_id=run_id,
            item_id=item_id,
            metric_name=result.metric_name,
            score=result.score,
            normalized_score=result.normalized_score,
            raw_output=result.raw_output,
            reasoning=result.reasoning,
            metadata_json=result.metadata,
            execution_time_ms=result.execution_time_ms,
            error=result.error,
        )

    async def save_many(self, results: Sequence[MetricResult]) -> None:
        """Save multiple metric results in batch."""
        if not results:
            return

        run_id = ""
        item_id = ""
        for r in results:
            meta = r.metadata or {}
            rid = meta.get("run_id", "")
            iid = meta.get("item_id", "")
            if rid:
                run_id = str(rid)
            if iid:
                item_id = str(iid)

        models = [self._to_model(r, run_id, item_id) for r in results]
        self._session.add_all(models)

    async def find_by_run_id(
        self,
        run_id: UUIDv7,
        metric_name: str | None = None,
    ) -> list[MetricResult]:
        """Find metric results by run ID."""
        stmt = select(MetricResultModel).where(
            MetricResultModel.run_id == str(run_id),
        )
        if metric_name:
            stmt = stmt.where(MetricResultModel.metric_name == metric_name)
        stmt = stmt.order_by(MetricResultModel.created_at)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def find_by_item_id(
        self,
        run_id: UUIDv7,
        item_id: UUIDv7,
    ) -> list[MetricResult]:
        """Find metric results for a specific item."""
        stmt = (
            select(MetricResultModel)
            .where(
                MetricResultModel.run_id == str(run_id),
                MetricResultModel.item_id == str(item_id),
            )
            .order_by(MetricResultModel.metric_name)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def list(self, query: MetricResultQuery) -> PaginatedMetricResults:
        """List metric results with filtering and pagination."""
        stmt = select(MetricResultModel)

        if query.run_id:
            stmt = stmt.where(MetricResultModel.run_id == query.run_id)
        if query.item_id:
            stmt = stmt.where(MetricResultModel.item_id == query.item_id)
        if query.metric_name:
            stmt = stmt.where(MetricResultModel.metric_name == query.metric_name)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar() or 0

        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)
        stmt = stmt.order_by(MetricResultModel.created_at)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return PaginatedMetricResults(
            items=[self._to_domain(m) for m in models],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    async def get_aggregation(
        self,
        run_id: UUIDv7,
        metric_name: str,
    ) -> MetricAggregation:
        """Compute aggregated scores for a metric across all items in a run."""
        results = await self.find_by_run_id(run_id, metric_name=metric_name)
        return MetricAggregation.from_results(metric_name, tuple(results))
