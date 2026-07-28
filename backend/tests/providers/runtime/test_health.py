"""Tests for runtime health."""

from app.providers.runtime.health.runtime_health import (
    HealthCheckResult,
    HealthStatus,
    RuntimeHealthAggregator,
)


class TestRuntimeHealthAggregator:
    """Tests for RuntimeHealthAggregator."""

    def test_empty_aggregation(self) -> None:
        agg = RuntimeHealthAggregator()
        result = agg.aggregate()
        assert result.status == HealthStatus.HEALTHY
        assert len(result.checks) == 0

    def test_all_healthy(self) -> None:
        agg = RuntimeHealthAggregator()
        agg.add_check(HealthCheckResult(name="a", status=HealthStatus.HEALTHY))
        agg.add_check(HealthCheckResult(name="b", status=HealthStatus.HEALTHY))
        result = agg.aggregate()
        assert result.status == HealthStatus.HEALTHY

    def test_degraded(self) -> None:
        agg = RuntimeHealthAggregator()
        agg.add_check(HealthCheckResult(name="a", status=HealthStatus.HEALTHY))
        agg.add_check(HealthCheckResult(name="b", status=HealthStatus.DEGRADED))
        result = agg.aggregate()
        assert result.status == HealthStatus.DEGRADED

    def test_unhealthy_overrides(self) -> None:
        agg = RuntimeHealthAggregator()
        agg.add_check(HealthCheckResult(name="a", status=HealthStatus.HEALTHY))
        agg.add_check(HealthCheckResult(name="b", status=HealthStatus.UNHEALTHY))
        result = agg.aggregate()
        assert result.status == HealthStatus.UNHEALTHY

    def test_reset(self) -> None:
        agg = RuntimeHealthAggregator()
        agg.add_check(HealthCheckResult(name="a", status=HealthStatus.HEALTHY))
        agg.reset()
        result = agg.aggregate()
        assert len(result.checks) == 0

    def test_result_immutability(self) -> None:
        result = HealthCheckResult(name="x", status=HealthStatus.HEALTHY, message="ok")
        try:
            result.name = "y"  # type: ignore[misc]
        except AttributeError:
            pass
        assert result.name == "x"

    def test_aggregate_health_immutability(self) -> None:
        agg = RuntimeHealthAggregator()
        agg.add_check(HealthCheckResult(name="a", status=HealthStatus.HEALTHY))
        result = agg.aggregate()
        try:
            result.status = HealthStatus.UNHEALTHY  # type: ignore[misc]
        except AttributeError:
            pass
        assert result.status == HealthStatus.HEALTHY
