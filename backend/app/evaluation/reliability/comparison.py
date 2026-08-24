"""Model comparison capability.

Compares two model outputs on the same evaluation configuration,
producing metric-level deltas, cost differences, and latency
differences. Does not invent a single "quality score" — metric
granularity is preserved.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.evaluation.replay.domain import ExecutionTrace


@dataclass(frozen=True, slots=True)
class MetricComparison:
    """Comparison of a single metric between two models."""

    metric_name: str
    model_a_score: float
    model_b_score: float
    absolute_difference: float
    direction: str  # "a_better", "b_better", "equal"
    model_a_cost_usd: float = 0.0
    model_b_cost_usd: float = 0.0
    model_a_latency_ms: int = 0
    model_b_latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class ModelComparison:
    """Full comparison between two model evaluation runs."""

    model_a_name: str
    model_b_name: str
    metric_comparisons: tuple[MetricComparison, ...] = ()
    a_better_count: int = 0
    b_better_count: int = 0
    tie_count: int = 0
    total_cost_difference: float = 0.0
    total_latency_difference: int = 0
    a_total_tokens: int = 0
    b_total_tokens: int = 0
    a_error_count: int = 0
    b_error_count: int = 0

    @property
    def winner(self) -> str:
        """Determine overall winner by metric majority."""
        if self.a_better_count > self.b_better_count:
            return "model_a"
        if self.b_better_count > self.a_better_count:
            return "model_b"
        return "tie"


def compare_models(
    trace_a: ExecutionTrace,
    trace_b: ExecutionTrace,
    *,
    model_a_name: str = "",
    model_b_name: str = "",
) -> ModelComparison:
    """Compare two execution traces from different models.

    Both traces must cover the same items (same item indices).
    """
    a_name = model_a_name or f"{trace_a.provider_name}/{trace_a.model_id}"
    b_name = model_b_name or f"{trace_b.provider_name}/{trace_b.model_id}"

    a_items = {it.item_index: it for it in trace_a.item_traces}
    b_items = {it.item_index: it for it in trace_b.item_traces}
    common = sorted(set(a_items.keys()) & set(b_items.keys()))

    metric_data: dict[str, dict[str, list[float]]] = {}
    a_better = 0
    b_better = 0
    ties = 0

    for idx in common:
        a_trace = a_items[idx]
        b_trace = b_items[idx]
        a_scores = {mt.metric_name: mt.normalized_score for mt in a_trace.metric_traces}
        b_scores = {mt.metric_name: mt.normalized_score for mt in b_trace.metric_traces}

        all_names = set(a_scores.keys()) | set(b_scores.keys())
        for name in all_names:
            if name not in metric_data:
                metric_data[name] = {
                    "a": [],
                    "b": [],
                    "a_cost": [],
                    "b_cost": [],
                    "a_lat": [],
                    "b_lat": [],
                }
            a_val = a_scores.get(name, 0.0)
            b_val = b_scores.get(name, 0.0)
            metric_data[name]["a"].append(a_val)
            metric_data[name]["b"].append(b_val)

            a_costs = {mt.metric_name: mt.cost_usd for mt in a_trace.metric_traces}
            b_costs = {mt.metric_name: mt.cost_usd for mt in b_trace.metric_traces}
            metric_data[name]["a_cost"].append(a_costs.get(name, 0.0))
            metric_data[name]["b_cost"].append(b_costs.get(name, 0.0))

            a_lats = {mt.metric_name: mt.execution_time_ms for mt in a_trace.metric_traces}
            b_lats = {mt.metric_name: mt.execution_time_ms for mt in b_trace.metric_traces}
            metric_data[name]["a_lat"].append(int(a_lats.get(name, 0)))
            metric_data[name]["b_lat"].append(int(b_lats.get(name, 0)))

    comparisons = []
    for name, data in metric_data.items():
        a_mean = sum(data["a"]) / len(data["a"]) if data["a"] else 0.0
        b_mean = sum(data["b"]) / len(data["b"]) if data["b"] else 0.0
        a_cost = sum(data["a_cost"]) if data["a_cost"] else 0.0
        b_cost = sum(data["b_cost"]) if data["b_cost"] else 0.0
        a_lat = int(sum(data["a_lat"])) if data["a_lat"] else 0
        b_lat = int(sum(data["b_lat"])) if data["b_lat"] else 0

        diff = b_mean - a_mean
        if diff > 0.01:
            direction = "b_better"
            b_better += 1
        elif diff < -0.01:
            direction = "a_better"
            a_better += 1
        else:
            direction = "equal"
            ties += 1

        comparisons.append(
            MetricComparison(
                metric_name=name,
                model_a_score=a_mean,
                model_b_score=b_mean,
                absolute_difference=abs(diff),
                direction=direction,
                model_a_cost_usd=a_cost,
                model_b_cost_usd=b_cost,
                model_a_latency_ms=a_lat,
                model_b_latency_ms=b_lat,
            )
        )

    return ModelComparison(
        model_a_name=a_name,
        model_b_name=b_name,
        metric_comparisons=tuple(comparisons),
        a_better_count=a_better,
        b_better_count=b_better,
        tie_count=ties,
        total_cost_difference=trace_b.total_cost_usd - trace_a.total_cost_usd,
        total_latency_difference=trace_b.duration_ms - trace_a.duration_ms,
        a_total_tokens=trace_a.total_tokens_input + trace_a.total_tokens_output,
        b_total_tokens=trace_b.total_tokens_input + trace_b.total_tokens_output,
        a_error_count=trace_a.failure_count,
        b_error_count=trace_b.failure_count,
    )
