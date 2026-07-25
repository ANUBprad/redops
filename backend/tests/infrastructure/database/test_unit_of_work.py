"""Tests for SqlAlchemyUnitOfWork and SqlAlchemyTransaction."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.transaction import SqlAlchemyTransaction
from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


class TestSqlAlchemyUnitOfWork:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        session = AsyncMock(spec=AsyncSession)
        session.in_transaction = MagicMock(return_value=False)
        return session

    @pytest.fixture
    def session_factory(self, mock_session: AsyncMock):
        """Create a session factory callable that returns the mock session."""
        return lambda: mock_session

    async def test_enter_exit_context(self, session_factory, mock_session: AsyncMock) -> None:
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow as ctx:
            assert ctx is uow
            assert uow.session is not None
        mock_session.close.assert_awaited_once()

    async def test_commit(self, session_factory, mock_session: AsyncMock) -> None:
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            await uow.commit()
        mock_session.commit.assert_awaited_once()

    async def test_rollback(self, session_factory, mock_session: AsyncMock) -> None:
        uow = SqlAlchemyUnitOfWork(session_factory)
        async with uow:
            await uow.rollback()
        mock_session.rollback.assert_awaited_once()

    async def test_rollback_on_exception(self, session_factory, mock_session: AsyncMock) -> None:
        uow = SqlAlchemyUnitOfWork(session_factory)
        with pytest.raises(ValueError):
            async with uow:
                msg = "test error"
                raise ValueError(msg)
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    async def test_session_property_before_enter(self, session_factory) -> None:
        uow = SqlAlchemyUnitOfWork(session_factory)
        with pytest.raises(RuntimeError):
            _ = uow.session


class TestSqlAlchemyTransaction:
    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        session = AsyncMock(spec=AsyncSession)
        session.in_transaction = MagicMock(return_value=False)
        return session

    async def test_begin_commit(self, mock_session: AsyncMock) -> None:
        tx = SqlAlchemyTransaction(mock_session)
        await tx.begin()
        assert tx.is_active is True
        await tx.commit()
        assert tx.is_active is False
        mock_session.commit.assert_awaited_once()

    async def test_begin_rollback(self, mock_session: AsyncMock) -> None:
        tx = SqlAlchemyTransaction(mock_session)
        await tx.begin()
        await tx.rollback()
        assert tx.is_active is False
        mock_session.rollback.assert_awaited_once()

    async def test_context_manager_success(self, mock_session: AsyncMock) -> None:
        tx = SqlAlchemyTransaction(mock_session)
        async with tx:
            assert tx.is_active is True
        assert tx.is_active is False
        mock_session.commit.assert_awaited_once()

    async def test_context_manager_exception(self, mock_session: AsyncMock) -> None:
        tx = SqlAlchemyTransaction(mock_session)
        with pytest.raises(RuntimeError):
            async with tx:
                msg = "fail"
                raise RuntimeError(msg)
        mock_session.rollback.assert_awaited_once()
