"""FastAPI application factory using the Composition Root.

Creates and configures a FastAPI application instance that uses
the infrastructure composition root for dependency management,
lifecycle management, and health reporting.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from structlog import get_logger

from app.api.router import api_router
from app.core.config import get_config
from app.infrastructure.composition.bootstrap import Bootstrap
from app.infrastructure.composition.container import InfrastructureContainer
from app.infrastructure.database.engine import DatabaseEngine
from app.infrastructure.event_bus.redis_event_bus import RedisStreamsEventBus
from app.infrastructure.middleware.security import (
    RateLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.infrastructure.observability.context import (
    CorrelationIdMiddleware,
    RequestContextMiddleware,
)
from app.infrastructure.temporal.client import TemporalClientFactory

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


def create_application() -> FastAPI:
    """Create and configure the FastAPI application using the composition root.

    Returns:
        A fully configured FastAPI application instance.

    """
    app_config = get_config()
    container = InfrastructureContainer(app_config)
    container.setup()

    bootstrap = Bootstrap(container)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
        """Manage the application lifecycle via the bootstrap.

        Args:
            app: The FastAPI application instance.

        Yields:
            None while the application runs.

        """
        logger = get_logger("redops_eval")
        logger.info(
            "Starting RedOps Eval",
            env=app_config.env,
            version=app_config.app_version,
        )

        app.state.bootstrap = bootstrap
        app.state.di_container = container.container

        await bootstrap.initialize()
        await bootstrap.start()

        di_container = container.container
        app.state.session_factory = di_container.resolve(DatabaseEngine).session_factory
        app.state.redis_client = di_container.resolve(RedisStreamsEventBus).redis
        app.state.temporal_client = di_container.resolve(TemporalClientFactory).client

        logger.info("Application started successfully")

        yield

        logger.info("Shutting down application")
        await bootstrap.stop()
        logger.info("Application shut down successfully")

    app = FastAPI(
        title=app_config.app_name,
        version=app_config.app_version,
        debug=app_config.debug,
        lifespan=lifespan,
        docs_url="/docs" if app_config.debug else None,
        redoc_url="/redoc" if app_config.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_config.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=200, window_seconds=60)

    app.include_router(api_router)

    return app
