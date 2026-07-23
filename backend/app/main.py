"""FastAPI application factory for RedOps Eval."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from redis import asyncio as aioredis
from structlog import get_logger
from temporalio.client import Client as TemporalClient

from app.api.router import api_router
from app.core.config import get_config
from app.db.session import create_engine_and_session_factory, dispose_engine
from app.logging.setup import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    """Manage application lifecycle: startup and shutdown.

    All external service connections are resilient:
    if a service is unavailable, the application logs a warning
    and continues operating in a degraded state. The /ready
    endpoint reports which dependencies are healthy.
    """
    config = get_config()
    configure_logging(config)

    logger = get_logger("redops_eval")
    logger.info("Starting RedOps Eval", env=config.env, version=config.app_version)

    # Initialize database engine and session factory
    engine, session_factory = create_engine_and_session_factory(
        database_url=config.database_url,
        min_pool_size=config.db_min_pool_size,
        max_pool_size=config.db_max_pool_size,
    )
    app.state.engine = engine
    app.state.session_factory = session_factory

    # Initialize Redis client (resilient — connection errors degrade, not crash)
    try:
        redis_client = aioredis.Redis(
            host=config.redis_host,
            port=config.redis_port,
            db=config.redis_db,
            decode_responses=True,
        )
        await redis_client.ping()
        app.state.redis_client = redis_client
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis unavailable, running in degraded mode", error=str(exc))
        app.state.redis_client = None

    # Initialize Temporal client (resilient)
    try:
        temporal_client = await TemporalClient.connect(
            target_host=f"{config.temporal_host}:{config.temporal_port}",
            namespace=config.temporal_namespace,
        )
        app.state.temporal_client = temporal_client
        logger.info("Temporal connected")
    except Exception as exc:
        logger.warning("Temporal unavailable, running in degraded mode", error=str(exc))
        app.state.temporal_client = None

    logger.info("Application started successfully")

    yield

    # Shutdown
    if app.state.redis_client is not None:
        await app.state.redis_client.close()
    await dispose_engine(engine)

    logger.info("Application shut down successfully")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        debug=config.debug,
        lifespan=lifespan,
        docs_url="/docs" if config.debug else None,
        redoc_url="/redoc" if config.debug else None,
    )

    app.include_router(api_router)

    return app
