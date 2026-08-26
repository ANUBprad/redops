"""Experiment comparison analytics service."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

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
    from app.evaluation.domain.contracts.experiment_contracts import ExperimentRepository


class ExperimentComparisonService:
    """Service for comparing runs within an experiment against a baseline."""

    def __init__(
        self,
        experiment_repo: ExperimentRepository,
        run_repo: RunRepository,
        metric_repo: MetricResultRepository,
    ) -> None:
        self._experiment_repo = experiment_repo
        self._run_repo = run_repo
        self._metric_repo = metric_repo

    async def compare_experiment_runs(
        self,
        experiment_id: str,
    ) -> ComparisonResult:
        """Compare all runs within an experiment, showing delta from baseline.

        Args:
            experiment_id: The experiment identifier.

        Returns:
            A ComparisonResult with per-run metrics and delta from baseline.

        """
        from app.kernel.entities.base import UUIDv7

        experiment = await self._experiment_repo.find_by_id(UUIDv7.from_string(experiment_id))
        if experiment is None:
            return ComparisonResult(
                title="Experiment Comparison",
                summary="Experiment not found",
            )

        # Get all runs for this experiment
        from app.evaluation.domain.contracts.evaluation_contracts import RunQuery

        run_query = RunQuery(page_size=1000)
        all_runs = await self._run_repo.list(run_query)

        # Filter runs belonging to this experiment
        experiment_runs = [
            r for r in all_runs if getattr(r, "experiment_id", None) == experiment_id
        ]

        if not experiment_runs:
            return ComparisonResult(
                title=f"Experiment: {experiment.name.value}",
                summary="No runs found in this experiment",
            )

        # Build per-run metrics
        compared_items: list[ComparedItem] = []
        for run in experiment_runs:
            compared_items.append(
                ComparedItem(
                    entity_id=str(run.id),
                    entity_name=run.evaluation_name,
                    entity_type="run",
                )
            )

        # Compute metrics per run
        metrics_list: list[ComparisonMetric] = []

        # Cost comparison
        cost_values: list[MetricValue] = []
        for run in experiment_runs:
            cost_values.append(
                MetricValue(
                    entity_id=str(run.id),
                    value=run.cost,
                    formatted_value=f"${run.cost:.4f}",
                )
            )
        metrics_list.append(
            ComparisonMetric(
                metric_name="Cost",
                values=tuple(cost_values),
                best_entity_id=min(experiment_runs, key=lambda r: r.cost).id
                if experiment_runs
                else "",
            )
        )

        # Latency comparison
        latency_values: list[MetricValue] = []
        for run in experiment_runs:
            latency_values.append(
                MetricValue(
                    entity_id=str(run.id),
                    value=float(run.average_latency_ms),
                    formatted_value=f"{run.average_latency_ms}ms",
                )
            )
        metrics_list.append(
            ComparisonMetric(
                metric_name="Latency",
                values=tuple(latency_values),
                best_entity_id=min(
                    (r for r in experiment_runs if r.average_latency_ms > 0),
                    key=lambda r: r.average_latency_ms,
                    default=experiment_runs[0],
                ).id
                if experiment_runs
                else "",
            )
        )

        # Token usage comparison
        token_values: list[MetricValue] = []
        for run in experiment_runs:
            token_values.append(
                MetricValue(
                    entity_id=str(run.id),
                    value=float(run.token_input + run.token_output),
                    formatted_value=str(run.token_input + run.token_output),
                )
            )
        metrics_list.append(
            ComparisonMetric(
                metric_name="Token Usage",
                values=tuple(token_values),
                best_entity_id="",
            )
        )

        # Build summary with baseline delta
        baseline_id = experiment.baseline_run_id
        summary_parts = [f"Compared {len(experiment_runs)} runs"]
        if baseline_id:
            summary_parts.append(f"baseline: {baseline_id[:8]}")

        return ComparisonResult(
            title=f"Experiment: {experiment.name.value}",
            compared_items=tuple(compared_items),
            metrics=tuple(metrics_list),
            summary=". ".join(summary_parts),
        )


class MetricDistributionService:
    """Service for metric distribution histograms."""

    def __init__(self, metric_repo: MetricResultRepository) -> None:
        self._metric_repo = metric_repo

    async def get_distribution(
        self,
        run_id: str | None = None,
        metric_name: str | None = None,
        bins: int = 10,
    ) -> dict[str, Any]:
        """Compute metric score distribution as histogram bins.

        Args:
            run_id: Optional run ID to filter by.
            metric_name: Optional metric name to filter by.
            bins: Number of histogram bins (default 10).

        Returns:
            Dictionary with bin edges and counts.

        """
        from app.kernel.entities.base import UUIDv7

        if run_id:
            results = await self._metric_repo.find_by_run_id(
                UUIDv7.from_string(run_id),
                metric_name=metric_name,
            )
        else:
            results = []

        scores = [r.score for r in results if r.error is None]

        if not scores:
            return {"bins": [], "counts": [], "total": 0, "metric_name": metric_name or ""}

        min_score = min(scores)
        max_score = max(scores)

        if min_score == max_score:
            return {
                "bins": [min_score],
                "counts": [len(scores)],
                "total": len(scores),
                "metric_name": metric_name or "",
            }

        bin_width = (max_score - min_score) / bins
        bin_edges = [round(min_score + i * bin_width, 4) for i in range(bins + 1)]
        bin_counts = [0] * bins

        for score in scores:
            idx = min(int((score - min_score) / bin_width), bins - 1)
            bin_counts[idx] += 1

        return {
            "bins": bin_edges,
            "counts": bin_counts,
            "total": len(scores),
            "metric_name": metric_name or "",
        }


class PassFailSummaryService:
    """Service for pass/fail summary by threshold."""

    def __init__(self, metric_repo: MetricResultRepository) -> None:
        self._metric_repo = metric_repo

    async def get_summary(
        self,
        run_id: str,
        thresholds: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Compute pass/fail summary for a run against thresholds.

        Args:
            run_id: The evaluation run identifier.
            thresholds: Optional metric_name -> threshold mapping.
                       Metrics with score >= threshold pass.

        Returns:
            Dictionary with per-metric pass/fail counts and overall verdict.

        """
        from app.kernel.entities.base import UUIDv7

        results = await self._metric_repo.find_by_run_id(
            UUIDv7.from_string(run_id),
        )

        metric_results: dict[str, list[float]] = defaultdict(list)
        for r in results:
            if r.error is None:
                metric_results[r.metric_name].append(r.score)

        summary: dict[str, Any] = {
            "run_id": run_id,
            "metrics": {},
            "overall_pass": True,
            "total_metrics": 0,
            "passed_metrics": 0,
            "failed_metrics": 0,
        }

        for metric_name, scores in metric_results.items():
            avg_score = sum(scores) / len(scores) if scores else 0.0
            threshold = (thresholds or {}).get(metric_name)
            passed = avg_score >= threshold if threshold is not None else True

            summary["metrics"][metric_name] = {
                "average_score": round(avg_score, 4),
                "threshold": threshold,
                "passed": passed,
                "sample_count": len(scores),
            }
            summary["total_metrics"] += 1
            if passed:
                summary["passed_metrics"] += 1
            else:
                summary["failed_metrics"] += 1
                summary["overall_pass"] = False

        return summary
