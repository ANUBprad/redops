"""Prometheus metrics for FastAPI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI

_metrics_registered = False


def setup_prometheus_metrics(app: FastAPI) -> None:
    """Configure Prometheus metrics endpoint.

    Exposes /metrics for Prometheus scraping.
    """
    global _metrics_registered
    if _metrics_registered:
        return

    try:
        from prometheus_client import (
            Counter,
            Gauge,
            Histogram,
            generate_latest,
        )

        REQUEST_COUNT = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )
        REQUEST_LATENCY = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds",
            ["method", "endpoint"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )
        EVALUATION_RUNS_ACTIVE = Gauge(
            "redops_evaluation_runs_active",
            "Number of currently active evaluation runs",
        )
        EVALUATION_RUNS_COMPLETED = Counter(
            "redops_evaluation_runs_completed_total",
            "Total completed evaluation runs",
        )
        ATTACK_VIOLATIONS = Counter(
            "redops_attack_violations_total",
            "Total attack violations detected",
        )
        SAFETY_SCORE = Gauge(
            "redops_safety_score_average",
            "Average safety score",
        )
        TOKEN_USAGE = Counter(
            "redops_token_usage_total",
            "Total tokens used",
            ["provider"],
        )
        COST_TOTAL = Counter(
            "redops_cost_total",
            "Total cost in USD",
            ["provider"],
        )

        async def metrics() -> Response:
            return Response(
                content=generate_latest(),
                media_type="text/plain",
            )

        app.add_api_route("/metrics", metrics, methods=["GET"])

        app.state.prometheus = {
            "request_count": REQUEST_COUNT,
            "request_latency": REQUEST_LATENCY,
            "evaluation_runs_active": EVALUATION_RUNS_ACTIVE,
            "evaluation_runs_completed": EVALUATION_RUNS_COMPLETED,
            "attack_violations": ATTACK_VIOLATIONS,
            "safety_score": SAFETY_SCORE,
            "token_usage": TOKEN_USAGE,
            "cost_total": COST_TOTAL,
        }
        _metrics_registered = True
    except ImportError:
        pass
