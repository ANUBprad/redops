"""Tests for health contributors."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.infrastructure.health.database import DatabaseHealthContributor
from app.infrastructure.health.redis import RedisHealthContributor
from app.infrastructure.health.temporal import TemporalHealthContributor
from app.kernel.health.health import HealthStatus


class TestDatabaseHealthContributor:
    @pytest.fixture
    def engine(self) -> AsyncMock:
        engine = AsyncMock()
        engine.health.return_value = True
        return engine

    async def test_healthy(self, engine: AsyncMock) -> None:
        contributor = DatabaseHealthContributor(engine)
        result = await contributor.check_health()
        assert result.status is HealthStatus.HEALTHY
        assert "reachable" in result.detail

    async def test_unhealthy(self, engine: AsyncMock) -> None:
        engine.health.return_value = False
        contributor = DatabaseHealthContributor(engine)
        result = await contributor.check_health()
        assert result.status is HealthStatus.UNHEALTHY

    async def test_exception(self, engine: AsyncMock) -> None:
        engine.health.side_effect = RuntimeError("connection failed")
        contributor = DatabaseHealthContributor(engine)
        result = await contributor.check_health()
        assert result.status is HealthStatus.UNHEALTHY

    async def test_contributor_name(self, engine: AsyncMock) -> None:
        contributor = DatabaseHealthContributor(engine)
        assert contributor.contributor_name == "database"


class TestRedisHealthContributor:
    @pytest.fixture
    def redis(self) -> AsyncMock:
        client = AsyncMock()
        client.ping.return_value = True
        return client

    async def test_healthy(self, redis: AsyncMock) -> None:
        contributor = RedisHealthContributor(redis)
        result = await contributor.check_health()
        assert result.status is HealthStatus.HEALTHY

    async def test_unhealthy(self, redis: AsyncMock) -> None:
        redis.ping.return_value = False
        contributor = RedisHealthContributor(redis)
        result = await contributor.check_health()
        assert result.status is HealthStatus.UNHEALTHY

    async def test_exception(self, redis: AsyncMock) -> None:
        redis.ping.side_effect = RuntimeError("timeout")
        contributor = RedisHealthContributor(redis)
        result = await contributor.check_health()
        assert result.status is HealthStatus.UNHEALTHY

    async def test_contributor_name(self, redis: AsyncMock) -> None:
        contributor = RedisHealthContributor(redis)
        assert contributor.contributor_name == "redis"


class TestTemporalHealthContributor:
    @pytest.fixture
    def temporal(self) -> AsyncMock:
        factory = AsyncMock()
        factory.health.return_value = True
        return factory

    async def test_healthy(self, temporal: AsyncMock) -> None:
        contributor = TemporalHealthContributor(temporal)
        result = await contributor.check_health()
        assert result.status is HealthStatus.HEALTHY

    async def test_unhealthy(self, temporal: AsyncMock) -> None:
        temporal.health.return_value = False
        contributor = TemporalHealthContributor(temporal)
        result = await contributor.check_health()
        assert result.status is HealthStatus.UNHEALTHY

    async def test_contributor_name(self, temporal: AsyncMock) -> None:
        contributor = TemporalHealthContributor(temporal)
        assert contributor.contributor_name == "temporal"
