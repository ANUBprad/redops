"""SqlAlchemyUnitOfWork implementing the Kernel UnitOfWork contract.

Provides transactional context management for async SQLAlchemy sessions,
ensuring proper commit/rollback semantics through the Kernel's UnitOfWork
abstraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from app.kernel.repositories.unit_of_work import UnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Async SQLAlchemy Unit of Work implementation.

    Manages a single async session within a transaction boundary.
    Commits on success, rolls back on exception, and always closes
    the session on exit.

    Usage:
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repo = MyRepository(uow.session)
            await repo.add(entity)
            await uow.commit()
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Initialize with session factory."""
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        """Return the managed session.

        Raises:
            RuntimeError: If the unit of work has not been entered.

        """
        if self._session is None:
            raise RuntimeError("UnitOfWork not started; use 'async with' to enter")
        return self._session

    async def __aenter__(self) -> Self:
        """Enter the transactional context and create a new session."""
        self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the transactional context and close the session."""
        if self._session is not None:
            if exc_type is not None:
                await self._session.rollback()
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self.session.rollback()
