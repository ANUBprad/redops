"""Observability setup — wires event listeners, metrics, and tracing.

Called from main.py after the application is created.
Registers SQLAlchemy event listeners to capture run lifecycle
events and ensures the SSE broadcaster is available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.infrastructure.observability.event_listener import _register_flush_listener
from app.infrastructure.observability.opentelemetry import setup_opentelemetry
from app.infrastructure.observability.prometheus import setup_prometheus_metrics

if TYPE_CHECKING:
    from fastapi import FastAPI


def setup_observability(app: FastAPI) -> None:
    """Register observability hooks after the app is configured.

    This hooks into the application startup lifecycle to register
    SQLAlchemy event listeners on the database engine, and sets up
    OpenTelemetry tracing and Prometheus metrics.
    """
    setup_opentelemetry(app)
    setup_prometheus_metrics(app)

    @app.on_event("startup")
    async def _register_listeners() -> None:
        session_factory: async_sessionmaker[Any] | None = getattr(
            app.state,
            "session_factory",
            None,
        )
        if session_factory is None:
            return

        sync_engine = session_factory.kw["bind"].sync_engine
        _register_flush_listener(sync_engine)
