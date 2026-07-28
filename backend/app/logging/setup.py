"""Structured logging configuration using Structlog.

Produces JSON logs in production and human-readable output in development.
Enriches log events with request ID, correlation ID, service name, and environment.
"""

from __future__ import annotations

import logging

import structlog
from structlog.processors import JSONRenderer, TimeStamper
from structlog.typing import EventDict, Processor

from app.core.config import AppConfig


def add_service_info(
    logger: structlog.BoundLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add static service metadata to every log event."""
    event_dict["service"] = "redops-eval"
    event_dict["environment"] = getattr(
        __import__("app.core.config", fromlist=["get_config"]).get_config(),
        "env",
        "unknown",
    )
    return event_dict


def configure_logging(config: AppConfig) -> None:
    """Configure Structlog with application-wide settings.

    Args:
        config: The application configuration containing log level and environment.

    """
    is_development = config.env == "development"

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_service_info,
        TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if is_development:
        # Console-friendly output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production
        processors = shared_processors + [
            JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set the root Python logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(config.app_log_level)

    # Suppress noisy third-party loggers
    for noisy_logger in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Ensure structlog's stdlib integration is used
    structlog.stdlib.recreate_defaults(log_level=getattr(logging, config.app_log_level, None))
