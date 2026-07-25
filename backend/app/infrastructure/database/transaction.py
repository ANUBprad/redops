"""SqlAlchemyTransaction implementing the Kernel Transaction contract.

Provides fine-grained transaction management within a session,
allowing explicit begin/commit/rollback operations that map
directly to SQLAlchemy's nested transaction support.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from app.kernel.repositories.unit_of_work import Transaction

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyTransaction(Transaction):
    """Async SQLAlchemy transaction implementation.

    Wraps a single session's transaction with explicit begin, commit,
    and rollback methods. Supports use as an async context manager
    for scoped transaction management.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with a database session."""
        self._session = session
        self._active = False

    @property
    def is_active(self) -> bool:
        """Return whether the transaction is currently active."""
        return self._active

    async def begin(self) -> None:
        """Begin a new transaction on the session."""
        if not self._session.in_transaction():
            self._active = True

    async def commit(self) -> None:
        """Commit the current transaction."""
        if self._active:
            await self._session.commit()
            self._active = False

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        if self._active:
            await self._session.rollback()
            self._active = False

    async def __aenter__(self) -> Self:
        """Enter the transaction context."""
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the transaction context with automatic rollback on error."""
        if self._active:
            if exc_type is not None:
                await self.rollback()
            else:
                await self.commit()
