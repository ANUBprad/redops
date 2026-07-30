"""Tests for SqlAlchemyRunLogRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.evaluation.observability.domain import RunLogEntry
from app.infrastructure.database.repositories.run_log_repository import (
    SqlAlchemyRunLogRepository,
)
from app.kernel.entities.base import UUIDv7


def _make_entry(**kwargs: object) -> RunLogEntry:
    return RunLogEntry(
        run_id=kwargs.get("run_id", UUIDv7()),
        level=kwargs.get("level", "INFO"),
        source=kwargs.get("source", "test"),
        message=kwargs.get("message", "test log"),
        metadata=kwargs.get("metadata", {}),
    )


@pytest.mark.asyncio
class TestSqlAlchemyRunLogRepository:
    async def test_save_adds_to_session(self) -> None:
        session = MagicMock()
        repo = SqlAlchemyRunLogRepository(session)
        entry = _make_entry()

        await repo.save(entry)

        session.add.assert_called_once()
        model = session.add.call_args[0][0]
        assert model.run_id == str(entry.run_id)
        assert model.level == "INFO"

    async def test_find_by_run_id(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        scalars = MagicMock()
        mock_model = MagicMock()
        mock_model.run_id = str(UUIDv7())
        mock_model.log_id = str(UUIDv7())
        mock_model.level = "INFO"
        mock_model.source = "test"
        mock_model.message = "log message"
        mock_model.metadata_json = {}
        mock_model.correlation_id = None
        mock_model.timestamp = None
        scalars.all.return_value = [mock_model]
        mock_result.scalars.return_value = scalars
        session.execute.return_value = mock_result

        repo = SqlAlchemyRunLogRepository(session)
        results = await repo.find_by_run_id(UUIDv7())

        assert len(results) == 1
        assert results[0].level == "INFO"
        assert results[0].message == "log message"

    async def test_count_by_run_id(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        session.execute.return_value = mock_result

        repo = SqlAlchemyRunLogRepository(session)
        count = await repo.count_by_run_id(UUIDv7())

        assert count == 3
