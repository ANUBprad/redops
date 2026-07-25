"""Logging configuration provider extending Kernel BaseConfiguration."""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.contracts.config import BaseConfiguration


@dataclass(frozen=True)
class LoggingConfiguration(BaseConfiguration):
    """Structured logging configuration.

    Controls log level, output format (JSON vs console), and
    enrichment features like correlation IDs and trace IDs.
    """

    level: str = "INFO"
    json_format: bool = False
    service_name: str = "redops-eval"
    enable_request_logging: bool = True
    enable_sql_logging: bool = False
    enable_temporal_logging: bool = True
    include_correlation_id: bool = True
    include_trace_id: bool = True
