"""SQLAlchemy repository for metric result persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Table, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.domain.contracts.evaluation_contracts import (
    MetricResultQuery,
    MetricResultRepository,
    PaginatedMetricResults,
)
from app.evaluation.metrics.domain import MetricAggregation, MetricResult
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.kernel.entities.base import UUIDv7


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
            created_at=model.created_at,
            confidence=model.confidence,
            version=model.version,
            cost_usd=model.cost_usd,
        )

    async def save_many(self, results: Sequence[MetricResult]) -> None:
        """Persist metric results idempotently via a database upsert.

        Identity is (run_id, item_id, metric_name), taken from each result's
        metadata; one row per identity is enforced by the unique index
        uq_metric_results_run_item_metric. A retry or a duplicate score
        request updates the existing row instead of inserting a second one.
        """
        if not results:
            return

        now = datetime.now(UTC)
        values = []
        for r in results:
            meta = r.metadata or {}
            values.append(
                {
                    "run_id": str(meta.get("run_id", "") or ""),
                    "item_id": str(meta.get("item_id", "") or ""),
                    "metric_name": r.metric_name,
                    "score": r.score,
                    "normalized_score": r.normalized_score,
                    "raw_output": r.raw_output,
                    "reasoning": r.reasoning,
                    "metadata": r.metadata,
                    "execution_time_ms": r.execution_time_ms,
                    "error": r.error,
                    "created_at": now,
                    "confidence": r.confidence,
                    "version": r.version,
                    "cost_usd": r.cost_usd,
                }
            )

        # ponytail: stmt is Any because each dialect's Insert subclass carries
        # its own on_conflict_do_update/excluded API; the dialect-typed version
        # would need two near-identical code paths.
        table: Table = cast("Table", MetricResultModel.__table__)
        bind = getattr(self._session, "bind", None)
        stmt: Any = (
            postgres_insert(table)
            if bind is not None and bind.dialect.name == "postgresql"
            else sqlite_insert(table)
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["run_id", "item_id", "metric_name"],
            set_={
                column: stmt.excluded[column]
                for column in (
                    "score",
                    "normalized_score",
                    "raw_output",
                    "reasoning",
                    "metadata",
                    "execution_time_ms",
                    "error",
                    "created_at",
                    "confidence",
                    "version",
                    "cost_usd",
                )
            },
        )
        await self._session.execute(stmt, values)

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

    async def find_by_date_range(
        self,
        since: datetime,
        until: datetime,
        metric_name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        owner_project_id: str | None = None,
    ) -> Sequence[MetricResult]:
        """Find metric results created within a date range."""
        stmt = select(MetricResultModel).where(
            MetricResultModel.created_at >= since,
            MetricResultModel.created_at <= until,
        )
        if owner_project_id is not None:
            stmt = (
                stmt.join(
                    EvaluationRunModel,
                    MetricResultModel.run_id == EvaluationRunModel.id,
                )
                .outerjoin(
                    EvaluationModel,
                    EvaluationRunModel.evaluation_id == EvaluationModel.id,
                )
                .where(
                    or_(
                        EvaluationModel.project_id == owner_project_id,
                        and_(
                            EvaluationRunModel.evaluation_id.is_(None),
                            EvaluationRunModel.metadata_.op("->>")("project_id")
                            == owner_project_id,
                        ),
                    )
                )
            )
        if metric_name is not None:
            stmt = stmt.where(MetricResultModel.metric_name == metric_name)
        if provider is not None or model is not None:
            run_subq = select(EvaluationRunModel.id)
            if provider is not None:
                run_subq = run_subq.where(EvaluationRunModel.provider == provider)
            if model is not None:
                run_subq = run_subq.where(EvaluationRunModel.model == model)
            stmt = stmt.where(MetricResultModel.run_id.in_(run_subq))
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]
