"""FastAPI application factory using the Composition Root.

Creates and configures a FastAPI application instance that uses
the infrastructure composition root for dependency management,
lifecycle management, and health reporting.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from structlog import get_logger

from app.api.router import api_router
from app.core.config import get_config
from app.infrastructure.composition.bootstrap import Bootstrap
from app.infrastructure.composition.container import InfrastructureContainer
from app.infrastructure.observability.context import (
    CorrelationIdMiddleware,
    RequestContextMiddleware,
)

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

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_router)

    return app
