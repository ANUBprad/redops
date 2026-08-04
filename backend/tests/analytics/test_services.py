"""Tests for analytics services."""

from __future__ import annotations

from datetime import UTC, datetime

from app.analytics.domain.entities import (
    TrendDirection,
    TrendPoint,
)
from app.analytics.services.trends_service import TrendsService


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
