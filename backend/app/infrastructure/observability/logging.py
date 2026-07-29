"""Structured logging enrichment for infrastructure components.

Provides structlog processors that enrich log events with
infrastructure-specific context such as correlation IDs,
trace IDs, and service metadata.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import structlog
from structlog.processors import JSONRenderer, TimeStamper

from app.infrastructure.observability.correlation import get_correlation_id, get_request_id
from app.infrastructure.observability.workflow_context import get_workflow_context

if TYPE_CHECKING:
    from structlog.typing import EventDict, Processor

    from app.infrastructure.config.logging import LoggingConfiguration


class LoggingEnricher:
    """Processors that enrich structlog events with infrastructure context.

    Attached as structlog processors to automatically add correlation
    IDs, request IDs, workflow context, and service metadata to every
    log event.
    """

    @staticmethod
    def add_correlation_id(
        logger: structlog.BoundLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Add the current correlation ID to the log event.

        Args:
            logger: The bound logger instance.
            method_name: The method that was called.
            event_dict: The current event dictionary.

        Returns:
            The enriched event dictionary.

        """
        cid = get_correlation_id()
        if cid:
            event_dict["correlation_id"] = cid
        return event_dict

    @staticmethod
    def add_request_id(
        logger: structlog.BoundLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Add the current request ID to the log event.

        Args:
            logger: The bound logger instance.
            method_name: The method that was called.
            event_dict: The current event dictionary.

        Returns:
            The enriched event dictionary.

        """
        rid = get_request_id()
        if rid:
            event_dict["request_id"] = rid
        return event_dict

    @staticmethod
    def add_workflow_context(
        logger: structlog.BoundLogger,
        method_name: str,
        event_dict: EventDict,
    ) -> EventDict:
        """Add the current workflow context to the log event.

        Args:
            logger: The bound logger instance.
            method_name: The method that was called.
            event_dict: The current event dictionary.

        Returns:
            The enriched event dictionary.

        """
        ctx = get_workflow_context()
        if ctx is not None:
            event_dict["workflow_id"] = ctx.get("workflow_id", "")
            event_dict["run_id"] = ctx.get("run_id", "")
            event_dict["workflow_type"] = ctx.get("workflow_type", "")
        return event_dict


def _add_service_info(
    _logger: structlog.BoundLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add static service metadata to every log event."""
    event_dict["service"] = "redops-eval"
    return event_dict


def configure_infrastructure_logging(config: LoggingConfiguration) -> None:
    """Configure structlog with infrastructure-aware processors.

    Args:
        config: The logging configuration.

    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_service_info,
        TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if config.include_correlation_id:
        shared_processors.append(LoggingEnricher.add_correlation_id)
    if config.include_trace_id:
        shared_processors.append(LoggingEnricher.add_request_id)
    shared_processors.append(LoggingEnricher.add_workflow_context)

    if config.json_format:
        processors = [*shared_processors, JSONRenderer()]
    else:
        processors = [*shared_processors, structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(config.level)

    for noisy_logger in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    structlog.stdlib.recreate_defaults(log_level=config.level)  # type: ignore[arg-type]
