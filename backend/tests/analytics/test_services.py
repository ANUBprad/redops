"""Tests for analytics services."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.analytics.domain.entities import (
    TrendDirection,
    TrendPoint,
)
from app.analytics.services.trends_service import TrendsService
from app.evaluation.domain.contracts.evaluation_contracts import (
    MetricResultRepository,
)
from app.evaluation.metrics.domain import MetricResult


class TestTrendsServiceDirection:
    def setup_method(self) -> None:
        self.service = TrendsService(run_repo=None, metric_repo=None)  # type: ignore[arg-type]

    def test_compute_direction_up(self) -> None:
        points = [
            TrendPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), value=0.5),
            TrendPoint(timestamp=datetime(2025, 1, 2, tzinfo=UTC), value=0.6),
        ]
        direction, change = self.service._compute_direction(points)
        assert direction == TrendDirection.UP
        assert change > 0

    def test_compute_direction_down(self) -> None:
        points = [
            TrendPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), value=0.6),
            TrendPoint(timestamp=datetime(2025, 1, 2, tzinfo=UTC), value=0.5),
        ]
        direction, change = self.service._compute_direction(points)
        assert direction == TrendDirection.DOWN
        assert change < 0

    def test_compute_direction_flat(self) -> None:
        points = [
            TrendPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), value=0.5),
            TrendPoint(timestamp=datetime(2025, 1, 2, tzinfo=UTC), value=0.5),
        ]
        direction, change = self.service._compute_direction(points)
        assert direction == TrendDirection.FLAT
        assert change == 0.0

    def test_compute_direction_single_point(self) -> None:
        points = [
            TrendPoint(timestamp=datetime(2025, 1, 1, tzinfo=UTC), value=0.5),
        ]
        direction, change = self.service._compute_direction(points)
        assert direction == TrendDirection.FLAT
        assert change == 0.0

    def test_compute_direction_empty(self) -> None:
        direction, change = self.service._compute_direction([])
        assert direction == TrendDirection.FLAT
        assert change == 0.0

    def test_bucket_key_day(self) -> None:
        dt = datetime(2025, 1, 15, 14, 30, 0, tzinfo=UTC)
        key = self.service._bucket_key(dt, "day")
        assert key == "2025-01-15T00:00:00+00:00"

    def test_bucket_key_week(self) -> None:
        dt = datetime(2025, 1, 15, 14, 30, 0, tzinfo=UTC)
        key = self.service._bucket_key(dt, "week")
        assert "2025-01-13" in key or "2025-01-12" in key

    def test_bucket_key_month(self) -> None:
        dt = datetime(2025, 1, 15, 14, 30, 0, tzinfo=UTC)
        key = self.service._bucket_key(dt, "month")
        assert key == "2025-01-01T00:00:00+00:00"


class TestTrendsServiceMetricTrendErrorExclusion:
    def test_error_results_are_excluded_from_metric_trend(self) -> None:
        """Failed metric results never drag trend averages toward zero."""
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)
        results = []
        for score, is_error in ((0.5, False), (0.7, False), (0.9, True)):
            mr = MagicMock(spec=MetricResult)
            mr.created_at = datetime(2025, 1, 15, 14, 30, 0, tzinfo=UTC)
            mr.normalized_score = score
            mr.error = "RuntimeError: boom" if is_error else None
            results.append(mr)
        mock_metric_repo.find_by_date_range = AsyncMock(return_value=results)

        import asyncio

        service = TrendsService(run_repo=None, metric_repo=mock_metric_repo)  # type: ignore[arg-type]
        series = asyncio.run(service.get_metric_trend(metric_name="correctness"))

        assert len(series.points) == 1
        point = series.points[0]
        assert point.value == 0.6
        assert point.label == "2 samples"
