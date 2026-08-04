"""Model comparison service."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.analytics.domain.entities import (
    ComparedItem,
    ComparisonMetric,
    ComparisonResult,
    MetricValue,
)

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import (
        MetricResultRepository,
        RunRepository,
    )
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun


class ComparisonService:
    """Service for model/provider comparison."""

    def __init__(
        self,
        run_repo: RunRepository,
        metric_repo: MetricResultRepository,
    ) -> None:
        self._run_repo = run_repo
        self._metric_repo = metric_repo

    async def compare(
        self,
        entity_type: str = "model",
        entity_ids: tuple[str, ...] = (),
        project_id: str | None = None,
        metrics: tuple[str, ...] = (),
        days: int = 30,
    ) -> ComparisonResult:
        """Compare models or providers."""
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        runs = await self._run_repo.find_by_date_range(
            since=since,
            until=now,
        )

        filtered_runs = [
            r
            for r in runs
            if not entity_ids
            or (entity_type == "model" and r.profile.model_id in entity_ids)
            or (entity_type == "provider" and r.profile.provider_name in entity_ids)
        ]

        grouped: dict[str, list[EvaluationRun]] = defaultdict(list)
        for run in filtered_runs:
            key = run.profile.model_id if entity_type == "model" else run.profile.provider_name
            grouped[key].append(run)

        compared_items = tuple(
            ComparedItem(
                entity_id=name,
                entity_name=name,
                entity_type=entity_type,
            )
            for name in sorted(grouped.keys())
        )

        comparison_metrics = self._compute_comparison_metrics(grouped, entity_type)

        return ComparisonResult(
            title=f"{'Model' if entity_type == 'model' else 'Provider'} Comparison",
            compared_items=compared_items,
            metrics=comparison_metrics,
            summary=(
                f"Compared {len(compared_items)} {entity_type}(s) "
                f"across {len(comparison_metrics)} metrics"
            ),
        )

    def _compute_comparison_metrics(
        self,
        grouped: dict[str, list[EvaluationRun]],
        entity_type: str,
    ) -> tuple[ComparisonMetric, ...]:
        """Compute comparison metrics across entities."""
        metrics_list: list[ComparisonMetric] = []

        score_values: list[MetricValue] = []
        latency_values: list[MetricValue] = []
        cost_values: list[MetricValue] = []

        best_score = -1.0
        best_latency = float("inf")
        best_cost = float("inf")
        best_score_id = ""
        best_latency_id = ""
        best_cost_id = ""

        for name, runs in grouped.items():
            total_items = sum(r.items_completed for r in runs)
            all_items = sum(r.items_total for r in runs)
            avg_score = (total_items / all_items * 100) if all_items > 0 else 0.0

            latencies = [r.average_latency_ms for r in runs if r.average_latency_ms > 0]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

            costs = [r.cost for r in runs]
            avg_cost = sum(costs) / len(costs) if costs else 0.0

            score_values.append(
                MetricValue(
                    entity_id=name, value=round(avg_score, 2), formatted_value=f"{avg_score:.1f}%"
                )
            )
            latency_values.append(
                MetricValue(
                    entity_id=name,
                    value=round(avg_latency, 1),
                    formatted_value=f"{avg_latency:.0f}ms",
                )
            )
            cost_values.append(
                MetricValue(
                    entity_id=name, value=round(avg_cost, 6), formatted_value=f"${avg_cost:.4f}"
                )
            )

            if avg_score > best_score:
                best_score = avg_score
                best_score_id = name
            if avg_latency < best_latency and avg_latency > 0:
                best_latency = avg_latency
                best_latency_id = name
            if avg_cost < best_cost and avg_cost > 0:
                best_cost = avg_cost
                best_cost_id = name

        metrics_list.append(
            ComparisonMetric(
                metric_name="Score", values=tuple(score_values), best_entity_id=best_score_id
            )
        )
        metrics_list.append(
            ComparisonMetric(
                metric_name="Latency", values=tuple(latency_values), best_entity_id=best_latency_id
            )
        )
        metrics_list.append(
            ComparisonMetric(
                metric_name="Cost", values=tuple(cost_values), best_entity_id=best_cost_id
            )
        )

        return tuple(metrics_list)
