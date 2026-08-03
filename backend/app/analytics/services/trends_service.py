"""Historical trends service.

Computes time-series trends for metrics, costs, latency, and safety scores.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.analytics.domain.entities import (
    TrendDirection,
    TrendPoint,
    TrendSeries,
)

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import (
        MetricResultRepository,
        RunRepository,
    )


class TrendsService:
    """Service for computing historical trends."""

    def __init__(
        self,
        run_repo: RunRepository,
        metric_repo: MetricResultRepository,
    ) -> None:
        self._run_repo = run_repo
        self._metric_repo = metric_repo

    async def get_metric_trend(
        self,
        metric_name: str = "score",
        project_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        days: int = 30,
        granularity: str = "day",
    ) -> TrendSeries:
        """Compute a metric trend over time.

        Args:
            metric_name: Name of the metric to trend.
            project_id: Optional project filter.
            provider: Optional provider filter.
            model: Optional model filter.
            days: Number of days to look back.
            granularity: Time bucket size (day, week, month).

        Returns:
            Time-series trend data.

        """
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        results = await self._metric_repo.find_by_date_range(
            since=since,
            until=now,
            metric_name=metric_name,
            provider=provider,
            model=model,
        )

        buckets: dict[str, list[float]] = defaultdict(list)
        for result in results:
            if result.created_at is None:
                continue
            bucket_key = self._bucket_key(result.created_at, granularity)
            buckets[bucket_key].append(result.normalized_score)

        points: list[TrendPoint] = []
        for bucket_key in sorted(buckets.keys()):
            scores = buckets[bucket_key]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            points.append(
                TrendPoint(
                    timestamp=datetime.fromisoformat(bucket_key),
                    value=round(avg_score, 4),
                    label=f"{len(scores)} samples",
                )
            )

        direction, change_pct = self._compute_direction(points)

        return TrendSeries(
            name=metric_name,
            points=tuple(points),
            direction=direction,
            change_percent=round(change_pct, 2),
        )

    async def get_cost_trend(
        self,
        project_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        days: int = 30,
        granularity: str = "day",
    ) -> TrendSeries:
        """Compute cost trend over time."""
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        runs = await self._run_repo.find_by_date_range(
            since=since,
            until=now,
            provider=provider,
            model=model,
        )

        buckets: dict[str, list[float]] = defaultdict(list)
        for run in runs:
            bucket_key = self._bucket_key(run.created_at, granularity)
            buckets[bucket_key].append(run.cost)

        points: list[TrendPoint] = []
        for bucket_key in sorted(buckets.keys()):
            costs = buckets[bucket_key]
            avg_cost = sum(costs) / len(costs) if costs else 0.0
            points.append(
                TrendPoint(
                    timestamp=datetime.fromisoformat(bucket_key),
                    value=round(avg_cost, 6),
                    label=f"{len(costs)} runs",
                )
            )

        direction, change_pct = self._compute_direction(points)

        return TrendSeries(
            name="cost",
            points=tuple(points),
            direction=direction,
            change_percent=round(change_pct, 2),
        )

    async def get_latency_trend(
        self,
        project_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        days: int = 30,
        granularity: str = "day",
    ) -> TrendSeries:
        """Compute latency trend over time."""
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        runs = await self._run_repo.find_by_date_range(
            since=since,
            until=now,
            provider=provider,
            model=model,
        )

        buckets: dict[str, list[int]] = defaultdict(list)
        for run in runs:
            if run.average_latency_ms > 0:
                bucket_key = self._bucket_key(run.created_at, granularity)
                buckets[bucket_key].append(run.average_latency_ms)

        points: list[TrendPoint] = []
        for bucket_key in sorted(buckets.keys()):
            latencies = buckets[bucket_key]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            points.append(
                TrendPoint(
                    timestamp=datetime.fromisoformat(bucket_key),
                    value=round(avg_latency, 1),
                    label=f"{len(latencies)} runs",
                )
            )

        direction, change_pct = self._compute_direction(points)

        return TrendSeries(
            name="latency",
            points=tuple(points),
            direction=direction,
            change_percent=round(change_pct, 2),
        )

    def _bucket_key(self, dt: datetime, granularity: str) -> str:
        """Compute a bucket key for time grouping."""
        if granularity == "week":
            week_start = dt - timedelta(days=dt.weekday())
            return week_start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        if granularity == "month":
            return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        return dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    def _compute_direction(self, points: list[TrendPoint]) -> tuple[TrendDirection, float]:
        """Compute trend direction and percentage change."""
        if len(points) < 2:
            return TrendDirection.FLAT, 0.0

        first_val = points[0].value
        last_val = points[-1].value

        if first_val == 0:
            return TrendDirection.FLAT, 0.0

        change_pct = ((last_val - first_val) / first_val) * 100

        if change_pct > 1.0:
            return TrendDirection.UP, change_pct
        if change_pct < -1.0:
            return TrendDirection.DOWN, change_pct
        return TrendDirection.FLAT, change_pct
