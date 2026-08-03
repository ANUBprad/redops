"""Tests for SqlAlchemyRunEventRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.observability.domain import TimelineEntry
from app.infrastructure.database.repositories.run_event_repository import (
    SqlAlchemyRunEventRepository,
)
from app.kernel.entities.base import UUIDv7


def _make_entry(**kwargs: object) -> TimelineEntry:
    return TimelineEntry(
        run_id=kwargs.get("run_id", UUIDv7()),
        event_type=kwargs.get("event_type", "test.event"),
        data=kwargs.get("data", {}),
    )


@pytest.mark.asyncio
class TestSqlAlchemyRunEventRepository:
    async def test_save_adds_to_session(self) -> None:
        session = MagicMock()
        repo = SqlAlchemyRunEventRepository(session)
        entry = _make_entry()

        await repo.save(entry)

        session.add.assert_called_once()
        added_model = session.add.call_args[0][0]
        assert added_model.id == str(entry.entry_id)
        assert added_model.run_id == str(entry.run_id)

    async def test_find_by_run_id(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        scalars = MagicMock()
        entry_id = str(UUIDv7())
        run_id = str(UUIDv7())
        mock_model = MagicMock()
        mock_model.id = entry_id
        mock_model.run_id = run_id
        mock_model.event_type = "test.event"
        mock_model.data = {}
        mock_model.correlation_id = None
        mock_model.occurred_at = None
        scalars.all.return_value = [mock_model]
        mock_result.scalars.return_value = scalars
        session.execute.return_value = mock_result

        repo = SqlAlchemyRunEventRepository(session)
        results = await repo.find_by_run_id(UUIDv7.from_string(run_id))

        assert len(results) == 1
        assert results[0].event_type == "test.event"

    async def test_count_by_run_id(self) -> None:
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        session.execute.return_value = mock_result

        repo = SqlAlchemyRunEventRepository(session)
        count = await repo.count_by_run_id(UUIDv7())

        assert count == 5
