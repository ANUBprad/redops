"""Replay service for executing and analyzing traces.

Provides the ability to replay evaluation runs from captured traces,
compare trace outputs, and generate replay reports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.evaluation.replay.domain import (
    ExecutionTrace,
    ItemTrace,
    MetricTrace,
)

logger = logging.getLogger(__name__)


class ReplayService:
    """Service for replaying and analyzing execution traces.

    Supports loading traces from storage, replaying evaluations
    with the same configuration, and generating comparison reports.
    """

    def __init__(self, trace_repository: Any | None = None) -> None:
        self._trace_repository = trace_repository

    async def load_trace(self, run_id: str) -> ExecutionTrace | None:
        """Load an execution trace by run ID."""
        if self._trace_repository is not None:
            data = await self._trace_repository.find_by_run_id(run_id)
            if data:
                return ExecutionTrace.from_dict(data)
        return None

    async def save_trace(self, trace: ExecutionTrace) -> None:
        """Save an execution trace."""
        if self._trace_repository is not None:
            await self._trace_repository.save(
                run_id=trace.run_id,
                trace_data=trace.to_dict(),
            )

    def generate_replay_report(self, trace: ExecutionTrace) -> ReplayReport:
        """Generate a detailed report from an execution trace.

        Analyzes the trace to produce a human-readable report
        explaining why each score was produced.
        """
        item_reports = []
        for item_trace in trace.item_traces:
            item_report = self._analyze_item(trace, item_trace)
            item_reports.append(item_report)

        summary = ReplaySummary(
            run_id=trace.run_id,
            evaluation_name=trace.evaluation_name,
            provider=trace.provider_name,
            model=trace.model_id,
            status=trace.status,
            total_items=trace.item_count,
            successful_items=trace.success_count,
            failed_items=trace.failure_count,
            total_cost_usd=trace.total_cost_usd,
            total_tokens_input=trace.total_tokens_input,
            total_tokens_output=trace.total_tokens_output,
            total_latency_ms=trace.duration_ms,
            metric_summaries=self._summarize_metrics(trace),
            started_at=trace.started_at,
            completed_at=trace.completed_at,
        )

        return ReplayReport(
            summary=summary,
            item_reports=tuple(item_reports),
            timeline=self._build_timeline(trace),
            configuration=trace.configuration,
        )

    def compare_traces(
        self,
        baseline: ExecutionTrace,
        comparison: ExecutionTrace,
    ) -> TraceComparison:
        """Compare two execution traces.

        Produces a detailed comparison showing deltas in metrics,
        latency, cost, and item-level differences.
        """
        baseline_items = {it.item_index: it for it in baseline.item_traces}
        comparison_items = {it.item_index: it for it in comparison.item_traces}

        common_indices = set(baseline_items.keys()) & set(comparison_items.keys())

        item_comparisons = []
        for idx in sorted(common_indices):
            bc = baseline_items[idx]
            cc = comparison_items[idx]
            item_comparisons.append(self._compare_items(idx, bc, cc))

        baseline_metrics = self._extract_all_metrics(baseline)
        comparison_metrics = self._extract_all_metrics(comparison)

        metric_deltas = {}
        all_metric_names = set(baseline_metrics.keys()) | set(comparison_metrics.keys())
        for name in all_metric_names:
            b_vals = baseline_metrics.get(name, [])
            c_vals = comparison_metrics.get(name, [])
            b_mean = sum(b_vals) / len(b_vals) if b_vals else 0.0
            c_mean = sum(c_vals) / len(c_vals) if c_vals else 0.0
            metric_deltas[name] = {
                "baseline_mean": b_mean,
                "comparison_mean": c_mean,
                "delta": c_mean - b_mean,
                "delta_pct": ((c_mean - b_mean) / b_mean * 100) if b_mean > 0 else 0.0,
            }

        cost_delta = comparison.total_cost_usd - baseline.total_cost_usd
        latency_delta = comparison.duration_ms - baseline.duration_ms

        winner = self._determine_winner(metric_deltas, cost_delta, latency_delta)

        return TraceComparison(
            baseline_run_id=baseline.run_id,
            comparison_run_id=comparison.run_id,
            baseline_provider=baseline.provider_name,
            comparison_provider=comparison.provider_name,
            baseline_model=baseline.model_id,
            comparison_model=comparison.model_id,
            metric_deltas=metric_deltas,
            cost_delta=cost_delta,
            latency_delta=latency_delta,
            item_comparisons=tuple(item_comparisons),
            winner=winner,
            confidence=self._compute_comparison_confidence(metric_deltas),
        )

    def _analyze_item(self, trace: ExecutionTrace, item: ItemTrace) -> ItemReport:
        """Analyze a single item trace."""
        prompt_preview = item.prompt_trace.prompt[:200]
        provider_response = ""
        provider_error = None
        if item.provider_trace:
            provider_response = item.provider_trace.response_content[:200]
            provider_error = item.provider_trace.error

        metric_explanations = []
        for mt in item.metric_traces:
            explanation = self._explain_metric(mt)
            metric_explanations.append(explanation)

        return ItemReport(
            item_index=item.item_index,
            prompt_preview=prompt_preview,
            provider_response_preview=provider_response,
            provider_error=provider_error,
            metric_explanations=tuple(metric_explanations),
            total_latency_ms=item.total_latency_ms,
            total_cost_usd=item.total_cost_usd,
            error=item.error,
        )

    def _explain_metric(self, metric: MetricTrace) -> MetricExplanation:
        """Generate an explanation for a metric score."""
        if metric.error:
            reason = f"Metric failed: {metric.error}"
        elif metric.confidence > 0.8:
            reason = f"High confidence ({metric.confidence:.2f}): {metric.reasoning}"
        elif metric.confidence > 0.5:
            reason = f"Moderate confidence ({metric.confidence:.2f}): {metric.reasoning}"
        else:
            reason = f"Low confidence ({metric.confidence:.2f}): {metric.reasoning}"

        return MetricExplanation(
            metric_name=metric.metric_name,
            score=metric.score,
            normalized_score=metric.normalized_score,
            confidence=metric.confidence,
            reasoning=metric.reasoning,
            explanation=reason,
            version=metric.version,
            judge_model=metric.judge_model,
        )

    def _summarize_metrics(self, trace: ExecutionTrace) -> dict[str, MetricSummary]:
        """Summarize all metrics across items."""
        metric_data: dict[str, list[float]] = {}
        for item in trace.item_traces:
            for mt in item.metric_traces:
                if mt.metric_name not in metric_data:
                    metric_data[mt.metric_name] = []
                metric_data[mt.metric_name].append(mt.normalized_score)

        summaries = {}
        for name, scores in metric_data.items():
            if scores:
                summaries[name] = MetricSummary(
                    metric_name=name,
                    mean=sum(scores) / len(scores),
                    min_score=min(scores),
                    max_score=max(scores),
                    count=len(scores),
                )
        return summaries

    def _build_timeline(self, trace: ExecutionTrace) -> tuple[TimelineEntry, ...]:
        """Build a timeline of events."""
        entries = []
        for event in trace.events:
            entries.append(
                TimelineEntry(
                    timestamp=event.timestamp,
                    event_type=event.event_type.value,
                    sequence=event.sequence,
                    duration_ms=event.duration_ms,
                    data=event.data,
                    error=event.error,
                )
            )
        return tuple(entries)

    def _extract_all_metrics(self, trace: ExecutionTrace) -> dict[str, list[float]]:
        """Extract all metric scores grouped by name."""
        result: dict[str, list[float]] = {}
        for item in trace.item_traces:
            for mt in item.metric_traces:
                if mt.metric_name not in result:
                    result[mt.metric_name] = []
                result[mt.metric_name].append(mt.normalized_score)
        return result

    def _compare_items(
        self,
        index: int,
        baseline: ItemTrace,
        comparison: ItemTrace,
    ) -> ItemComparison:
        """Compare two item traces."""
        baseline_metrics = {mt.metric_name: mt.normalized_score for mt in baseline.metric_traces}
        comparison_metrics = {
            mt.metric_name: mt.normalized_score for mt in comparison.metric_traces
        }

        metric_deltas = {}
        all_names = set(baseline_metrics.keys()) | set(comparison_metrics.keys())
        for name in all_names:
            b_score = baseline_metrics.get(name, 0.0)
            c_score = comparison_metrics.get(name, 0.0)
            metric_deltas[name] = {
                "baseline": b_score,
                "comparison": c_score,
                "delta": c_score - b_score,
            }

        return ItemComparison(
            item_index=index,
            metric_deltas=metric_deltas,
            latency_delta=comparison.total_latency_ms - baseline.total_latency_ms,
            cost_delta=comparison.total_cost_usd - baseline.total_cost_usd,
        )

    def _determine_winner(
        self,
        metric_deltas: dict[str, dict[str, float]],
        cost_delta: float,
        latency_delta: float,
    ) -> str:
        """Determine the winner based on metric deltas."""
        positive_deltas = sum(1 for d in metric_deltas.values() if d["delta"] > 0.01)
        negative_deltas = sum(1 for d in metric_deltas.values() if d["delta"] < -0.01)

        if positive_deltas > negative_deltas:
            return "comparison"
        if negative_deltas > positive_deltas:
            return "baseline"
        return "tie"

    def _compute_comparison_confidence(self, metric_deltas: dict[str, dict[str, float]]) -> float:
        """Compute confidence in the comparison result."""
        if not metric_deltas:
            return 0.0

        deltas = [abs(d["delta"]) for d in metric_deltas.values()]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0

        return min(1.0, avg_delta * 10)


# --- Value objects for reports ---


@dataclass(frozen=True, slots=True)
class MetricExplanation:
    """Explanation of a metric score for replay."""

    metric_name: str
    score: float
    normalized_score: float
    confidence: float
    reasoning: str
    explanation: str
    version: str = "1.0.0"
    judge_model: str = ""


@dataclass(frozen=True, slots=True)
class ItemReport:
    """Report for a single item in a replay."""

    item_index: int
    prompt_preview: str
    provider_response_preview: str
    provider_error: str | None = None
    metric_explanations: tuple[MetricExplanation, ...] = ()
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MetricSummary:
    """Summary of a metric across all items."""

    metric_name: str
    mean: float
    min_score: float
    max_score: float
    count: int


@dataclass(frozen=True, slots=True)
class ReplaySummary:
    """Summary of a replay execution."""

    run_id: str
    evaluation_name: str
    provider: str
    model: str
    status: str
    total_items: int
    successful_items: int
    failed_items: int
    total_cost_usd: float
    total_tokens_input: int
    total_tokens_output: int
    total_latency_ms: int
    metric_summaries: dict[str, MetricSummary] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """A single entry in the execution timeline."""

    timestamp: datetime
    event_type: str
    sequence: int
    duration_ms: int = 0
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ReplayReport:
    """Full replay report with summary, items, and timeline."""

    summary: ReplaySummary
    item_reports: tuple[ItemReport, ...] = ()
    timeline: tuple[TimelineEntry, ...] = ()
    configuration: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ItemComparison:
    """Comparison of a single item between two traces."""

    item_index: int
    metric_deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    latency_delta: int = 0
    cost_delta: float = 0.0


@dataclass(frozen=True, slots=True)
class TraceComparison:
    """Comparison between two execution traces."""

    baseline_run_id: str
    comparison_run_id: str
    baseline_provider: str
    comparison_provider: str
    baseline_model: str
    comparison_model: str
    metric_deltas: dict[str, dict[str, float]] = field(default_factory=dict)
    cost_delta: float = 0.0
    latency_delta: int = 0
    item_comparisons: tuple[ItemComparison, ...] = ()
    winner: str = "tie"
    confidence: float = 0.0
