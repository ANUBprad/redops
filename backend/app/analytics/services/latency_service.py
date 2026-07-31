"""Latency analytics service."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, timedelta
from typing import TYPE_CHECKING

from app.analytics.domain.entities import (
    LatencyAnalysis,
    ModelLatency,
    ProviderLatency,
)

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import RunRepository


class LatencyService:
    """Service for latency analysis."""

    def __init__(self, run_repo: RunRepository) -> None:
        self._run_repo = run_repo

    async def get_analysis(
        self,
        project_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        days: int = 30,
    ) -> LatencyAnalysis:
        """Compute latency analysis."""
        now = __import__("datetime").datetime.now(UTC)
        since = now - timedelta(days=days)

        runs = await self._run_repo.find_by_date_range(
            since=since,
            until=now,
            provider=provider,
            model=model,
        )

        latencies = [r.average_latency_ms for r in runs if r.average_latency_ms > 0]

        if not latencies:
            return LatencyAnalysis()

        sorted_lat = sorted(latencies)
        count = len(sorted_lat)

        avg_latency = sum(sorted_lat) / count
        median_latency = sorted_lat[count // 2]
        p95_idx = min(int(count * 0.95), count - 1)
        p99_idx = min(int(count * 0.99), count - 1)

        provider_lat = self._compute_provider_latencies(runs)
        model_lat = self._compute_model_latencies(runs)

        return LatencyAnalysis(
            average_latency_ms=round(avg_latency, 1),
            median_latency_ms=round(median_latency, 1),
            p95_latency_ms=round(sorted_lat[p95_idx], 1),
            p99_latency_ms=round(sorted_lat[p99_idx], 1),
            min_latency_ms=round(sorted_lat[0], 1),
            max_latency_ms=round(sorted_lat[-1], 1),
            latency_by_provider=provider_lat,
            latency_by_model=model_lat,
        )

    def _compute_provider_latencies(self, runs: list[object]) -> tuple[ProviderLatency, ...]:
        """Group latencies by provider."""
        provider_data: dict[str, list[int]] = defaultdict(list)
        for run in runs:
            p = getattr(run, "provider", "unknown")
            lat = getattr(run, "average_latency_ms", 0)
            if lat > 0:
                provider_data[p].append(lat)

        result = []
        for prov, lats in provider_data.items():
            result.append(
                ProviderLatency(
                    provider=prov,
                    average_latency_ms=round(sum(lats) / len(lats), 1),
                    run_count=len(lats),
                )
            )
        return tuple(sorted(result, key=lambda x: x.average_latency_ms))

    def _compute_model_latencies(self, runs: list[object]) -> tuple[ModelLatency, ...]:
        """Group latencies by model."""
        model_data: dict[str, dict[str, object]] = defaultdict(lambda: {"lats": [], "provider": ""})
        for run in runs:
            m = getattr(run, "model", "unknown")
            lat = getattr(run, "average_latency_ms", 0)
            if lat > 0:
                model_data[m]["lats"].append(lat)
                model_data[m]["provider"] = getattr(run, "provider", "")

        result = []
        for mod, data in model_data.items():
            lats = data["lats"]  # type: ignore[arg-type]
            result.append(
                ModelLatency(
                    model=mod,
                    provider=str(data["provider"]),
                    average_latency_ms=round(sum(lats) / len(lats), 1),
                    run_count=len(lats),
                )
            )
        return tuple(sorted(result, key=lambda x: x.average_latency_ms))
