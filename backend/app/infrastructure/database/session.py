"""Session lifecycle management for the async SQLAlchemy session.

Provides the SessionManager which creates and manages async sessions,
handling commit, rollback, and close lifecycle for each request or
unit of work scope.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.infrastructure.database.engine import DatabaseEngine


class SessionManager:
    """Manages the lifecycle of async SQLAlchemy sessions.

    Provides factory methods for creating sessions within a managed
    lifecycle. Sessions created through this manager are automatically
    committed on success and rolled back on exception when used as
    an async context manager.
    """

    def __init__(self, database_engine: DatabaseEngine) -> None:
        """Initialize with database engine."""
        self._database_engine = database_engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the underlying session factory."""
        return self._database_engine.session_factory

    def create_session(self) -> AsyncSession:
        """Create a new async session."""
        return self.session_factory()

    @asynccontextmanager
    async def auto_session(self) -> AsyncGenerator[AsyncSession, Any]:
        """Provide an auto-committing session via async context manager.

        The session is committed on successful exit and rolled back
        if an exception occurs.

        Yields:
            An AsyncSession instance.

        """
        session = self.create_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """Close all sessions managed by this manager.

        Currently a no-op since sessions are managed individually.
        """
