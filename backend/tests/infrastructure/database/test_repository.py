"""Tests for SqlAlchemyRepository.

Uses a real SQLAlchemy declarative model to satisfy SQLAlchemy's
select() type requirements.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped as Mapped
from sqlalchemy.orm import mapped_column

from app.infrastructure.database.repository import SqlAlchemyRepository
from app.kernel.entities.base import UUIDv7
from app.kernel.results.result import Failure, Success


class _Base(DeclarativeBase):
    pass


class _TestModel(_Base):
    __tablename__ = "test_models"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(default="")


class TestSqlAlchemyRepository:
    @pytest.fixture
    def session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def repo(self, session: AsyncMock) -> SqlAlchemyRepository[Any]:
        return SqlAlchemyRepository(session, _TestModel)

    async def test_find_by_id_found(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity_id = UUIDv7()
        model = _TestModel(id=str(entity_id.value), name="test")
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = model
        session.execute = AsyncMock(return_value=scalar_result)

        result = await repo.find_by_id(entity_id)

        assert isinstance(result, Success)
        assert result.value == model

    async def test_find_by_id_not_found(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity_id = UUIDv7()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=scalar_result)

        result = await repo.find_by_id(entity_id)

        assert isinstance(result, Failure)
        assert "not found" in str(result.error)

    async def test_exists_true(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity_id = UUIDv7()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = _TestModel(id=str(entity_id.value))
        session.execute = AsyncMock(return_value=scalar_result)

        exists = await repo.exists(entity_id)

        assert exists is True

    async def test_exists_false(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity_id = UUIDv7()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=scalar_result)

        exists = await repo.exists(entity_id)

        assert exists is False

    async def test_add(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity = _TestModel(id="test-id", name="test")
        await repo.add(entity)
        session.add.assert_called_once_with(entity)

    async def test_update(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity = _TestModel(id="test-id", name="updated")
        session.merge = AsyncMock(return_value=entity)
        await repo.update(entity)
        session.merge.assert_called_once_with(entity)

    async def test_delete_found(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity_id = UUIDv7()
        model = _TestModel(id=str(entity_id.value))
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = model
        session.execute = AsyncMock(return_value=scalar_result)
        session.delete = AsyncMock()

        result = await repo.delete(entity_id)

        assert isinstance(result, Success)
        session.delete.assert_called_once_with(model)

    async def test_delete_not_found(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        entity_id = UUIDv7()
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=scalar_result)

        result = await repo.delete(entity_id)

        assert isinstance(result, Failure)
        assert "not found" in str(result.error)

    async def test_count(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        scalar_result = MagicMock()
        scalar_result.scalar_one.return_value = 5
        session.execute = AsyncMock(return_value=scalar_result)

        count = await repo.count()

        assert count == 5

    async def test_count_with_filters(self, repo: SqlAlchemyRepository[Any], session: AsyncMock) -> None:
        scalar_result = MagicMock()
        scalar_result.scalar_one.return_value = 2
        session.execute = AsyncMock(return_value=scalar_result)

        count = await repo.count(name="test")

        assert count == 2
