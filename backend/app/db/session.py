"""Async SQLAlchemy 2.0 engine and session factory initialization."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine_and_session_factory(
    database_url: str,
    min_pool_size: int = 5,
    max_pool_size: int = 20,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create and return an async engine and session factory.

    Args:
        database_url: Full async PostgreSQL connection URL.
        min_pool_size: Minimum number of connections in the pool.
        max_pool_size: Maximum number of connections in the pool.

    Returns:
        A tuple of (engine, session_factory).

    """
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=min_pool_size,
        max_overflow=max_pool_size - min_pool_size,
        pool_pre_ping=True,
    )

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    return engine, session_factory


async def dispose_engine(engine: AsyncEngine) -> None:
    """Dispose of the database engine and free pool resources."""
    await engine.dispose()
