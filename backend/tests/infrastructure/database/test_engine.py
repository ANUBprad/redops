"""Tests for DatabaseEngine."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.config.database import DatabaseConfiguration
from app.infrastructure.database.engine import DatabaseEngine
from app.kernel.lifecycle.lifecycle import LifecycleService


class TestDatabaseEngine:
    @pytest.fixture
    def config(self) -> DatabaseConfiguration:
        return DatabaseConfiguration(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            database="testdb",
        )

    def test_implements_lifecycle_service(self, config: DatabaseConfiguration) -> None:
        engine = DatabaseEngine(config)
        assert isinstance(engine, LifecycleService)

    def test_engine_property_before_init_raises(self, config: DatabaseConfiguration) -> None:
        engine = DatabaseEngine(config)
        with pytest.raises(RuntimeError):
            _ = engine.engine

    def test_session_factory_property_before_init_raises(self, config: DatabaseConfiguration) -> None:
        engine = DatabaseEngine(config)
        with pytest.raises(RuntimeError):
            _ = engine.session_factory

    async def test_health_when_not_initialized(self, config: DatabaseConfiguration) -> None:
        engine = DatabaseEngine(config)
        assert await engine.health() is False

    async def test_initialize_and_dispose(self, config: DatabaseConfiguration) -> None:
        engine = DatabaseEngine(config)
        mock_engine = AsyncMock()
        mock_engine.dispose = AsyncMock()

        with patch("app.infrastructure.database.engine.create_async_engine", return_value=mock_engine):
            await engine.initialize()
            assert engine._engine is not None
            assert engine._session_factory is not None

            await engine.dispose()
            mock_engine.dispose.assert_awaited_once()
            assert engine._engine is None
