"""Async SQLAlchemy engine lifecycle management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.kernel.lifecycle.lifecycle import LifecycleService

if TYPE_CHECKING:
    from app.infrastructure.config.database import DatabaseConfiguration


class DatabaseEngine(LifecycleService):
    """Manages the lifecycle of the async SQLAlchemy engine.

    Encapsulates engine creation, connection pooling configuration,
    and graceful disposal. Implements LifecycleService for integration
    with the application lifecycle manager.
    """

    def __init__(self, config: DatabaseConfiguration) -> None:
        """Initialize with database configuration."""
        self._config = config
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Return the configured async engine.

        Raises:
            RuntimeError: If the engine has not been initialized.

        """
        if self._engine is None:
            raise RuntimeError("Database engine not initialized")  # noqa: TRY003
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Return the session factory bound to this engine.

        Raises:
            RuntimeError: If the session factory has not been initialized.

        """
        if self._session_factory is None:
            raise RuntimeError("Database engine not initialized")  # noqa: TRY003
        return self._session_factory

    async def initialize(self) -> None:
        """Create the async engine and session factory."""
        config = self._config
        self._engine = create_async_engine(
            config.database_url,
            echo=config.echo,
            pool_size=config.min_pool_size,
            max_overflow=config.max_overflow,
            pool_pre_ping=config.pool_pre_ping,
            connect_args={
                "timeout": config.connect_timeout_seconds,
                "command_timeout": config.statement_timeout_seconds,
            },
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def start(self) -> None:
        """Verify the engine connection pool is operational."""
        async with self.engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))

    async def stop(self) -> None:
        """Dispose of the engine and free pool resources."""
        await self.dispose()

    async def dispose(self) -> None:
        """Dispose of the database engine."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    async def health(self) -> bool:
        """Check if the database engine is reachable."""
        if self._engine is None:
            return False
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1"),
                )
                row = result.fetchone()
                return row is not None and row[0] == 1
        except Exception:  # noqa: BLE001
            return False
