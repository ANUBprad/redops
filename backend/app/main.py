"""FastAPI application factory for RedOps Eval.

This module provides a lightweight entry point that delegates
all application wiring to the infrastructure composition root.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.infrastructure.composition.application import create_application
from app.infrastructure.observability.setup import setup_observability


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Delegates to the infrastructure composition root for all
    dependency wiring, lifecycle management, and configuration.

    Returns:
        A fully configured FastAPI application instance.

    """
    app = create_application()
    setup_observability(app)
    return app


app = create_app()
