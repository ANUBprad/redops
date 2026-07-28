"""Tests for SessionManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.engine import DatabaseEngine
from app.infrastructure.database.session import SessionManager


class TestSessionManager:
    @pytest.fixture
    def engine(self) -> AsyncMock:
        mock_factory = MagicMock()
        mock_session = AsyncMock(spec=AsyncSession)
        mock_factory.return_value = mock_session

        engine = AsyncMock(spec=DatabaseEngine)
        engine.session_factory = mock_factory
        engine._engine = MagicMock()
        return engine

    def test_create_session(self, engine: AsyncMock) -> None:
        manager = SessionManager(engine)
        session = manager.create_session()
        assert session is not None

    async def test_auto_session_commit(self, engine: AsyncMock) -> None:
        manager = SessionManager(engine)
        manager.create_session()

        async with manager.auto_session() as s:
            assert s is not None
