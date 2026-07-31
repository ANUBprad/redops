"""Cost analytics service."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.analytics.domain.entities import (
    CostAnalysis,
    ModelCost,
    ProviderCost,
)

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import RunRepository


class CostService:
    """Service for cost analysis."""

    def __init__(self, run_repo: RunRepository) -> None:
        self._run_repo = run_repo

    async def get_analysis(
        self,
        project_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        days: int = 30,
    ) -> CostAnalysis:
        """Compute cost analysis."""
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        from app.evaluation.domain.contracts.evaluation_contracts import RunQuery

        query = RunQuery(
            provider=provider,
            model=model,
            page=1,
            page_size=10000,
        )
        result = await self._run_repo.list(query)

        runs = [r for r in result.items if r.created_at and r.created_at >= since]

        total_cost = sum(r.cost for r in runs)
        run_count = len(runs)
        total_items = sum(r.items_completed for r in runs)

        avg_cost_per_run = total_cost / run_count if run_count > 0 else 0.0
        avg_cost_per_item = total_cost / total_items if total_items > 0 else 0.0

        cost_by_provider = self._compute_provider_costs(runs)
        cost_by_model = self._compute_model_costs(runs)
        projected = self._project_monthly_cost(runs, days)

        return CostAnalysis(
            total_cost=round(total_cost, 6),
            average_cost_per_run=round(avg_cost_per_run, 6),
            average_cost_per_item=round(avg_cost_per_item, 6),
            cost_by_provider=cost_by_provider,
            cost_by_model=cost_by_model,
            projected_monthly_cost=round(projected, 6),
        )

    def _compute_provider_costs(self, runs: list[object]) -> tuple[ProviderCost, ...]:
        provider_data: dict[str, dict[str, float]] = defaultdict(
            lambda: {"cost": 0.0, "count": 0.0}
        )
        for run in runs:
            p = getattr(run, "provider", "unknown")
            provider_data[p]["cost"] += getattr(run, "cost", 0.0)
            provider_data[p]["count"] += 1

        result = []
        for prov, data in provider_data.items():
            count = int(data["count"])
            result.append(
                ProviderCost(
                    provider=prov,
                    total_cost=round(data["cost"], 6),
                    run_count=count,
                    average_cost_per_run=round(data["cost"] / count, 6) if count > 0 else 0.0,
                )
            )
        return tuple(sorted(result, key=lambda x: x.total_cost, reverse=True))

    def _compute_model_costs(self, runs: list[object]) -> tuple[ModelCost, ...]:
        model_data: dict[str, dict[str, float | str]] = defaultdict(
            lambda: {"cost": 0.0, "count": 0.0, "provider": ""}
        )
        for run in runs:
            m = getattr(run, "model", "unknown")
            model_data[m]["cost"] += getattr(run, "cost", 0.0)
            model_data[m]["count"] += 1
            model_data[m]["provider"] = getattr(run, "provider", "")

        result = []
        for mod, data in model_data.items():
            count = int(data["count"])
            result.append(
                ModelCost(
                    model=mod,
                    provider=str(data["provider"]),
                    total_cost=round(float(data["cost"]), 6),
                    run_count=count,
                    average_cost_per_run=round(float(data["cost"]) / count, 6)
                    if count > 0
                    else 0.0,
                )
            )
        return tuple(sorted(result, key=lambda x: x.total_cost, reverse=True))

    def _project_monthly_cost(self, runs: list[object], days: int) -> float:
        """Project monthly cost based on recent data."""
        if not runs or days <= 0:
            return 0.0
        total_cost = sum(getattr(r, "cost", 0.0) for r in runs)
        daily_rate = total_cost / days
        return daily_rate * 30
