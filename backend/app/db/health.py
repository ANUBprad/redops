"""Database health check utility."""

from structlog import get_logger

logger = get_logger("redops_eval.db.health")


async def check_database_health() -> bool:
    """Check if the database is reachable by executing a simple query.

    Returns:
        True if the database is reachable, False otherwise.

    """
    from app.core.config import get_config
    from app.db.session import create_engine_and_session_factory

    config = get_config()

    engine, _ = create_engine_and_session_factory(
        database_url=config.database_url,
        min_pool_size=1,
        max_pool_size=1,
    )

    try:
        async with engine.connect() as connection:
            result = await connection.execute(__import__("sqlalchemy").text("SELECT 1"))
            row = result.fetchone()
            return row is not None and row[0] == 1
    except Exception as exc:
        logger.error("Database health check failed", error=str(exc))
        return False
    finally:
        await engine.dispose()
