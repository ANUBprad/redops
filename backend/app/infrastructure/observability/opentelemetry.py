"""OpenTelemetry setup for distributed tracing and metrics."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def setup_opentelemetry(app: FastAPI) -> None:
    """Configure OpenTelemetry tracing and metrics.

    In production, configure with actual exporter endpoints.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        resource = Resource.create(
            {
                "service.name": "redops-api",
                "service.version": "0.1.0",
            }
        )
        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
    except ImportError:
        pass
