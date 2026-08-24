"""Evaluation regression analysis.

Compares a current evaluation run against a baseline and determines
whether the current version passes or fails regression criteria.

Respects metric direction (higher-is-better vs lower-is-better),
applies configurable tolerance, handles missing metrics and errors
explicitly, and checks fingerprint compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.evaluation.metrics.domain import ScoreDirection


class RegressionVerdict(Enum):
    """Overall regression verdict."""

    PASS = "pass"
    FAIL = "fail"
    NOT_COMPARABLE = "not_comparable"
    ERROR = "error"


class MetricStatus(Enum):
    """Status of a single metric comparison."""

    PASS = "pass"
    REGRESSION = "regression"
    IMPROVEMENT = "improvement"
    NO_CHANGE = "no_change"
    NOT_COMPARABLE = "not_comparable"
    ADDED = "added"
    REMOVED = "removed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class MetricRegression:
    """Regression analysis for a single metric."""

    metric_name: str
    baseline_score: float | None
    current_score: float | None
    delta: float
    direction: ScoreDirection
    tolerance: float
    status: MetricStatus
    reasoning: str = ""


@dataclass(frozen=True, slots=True)
class RegressionConfig:
    """Configuration for regression analysis."""

    default_tolerance: float = 0.02
    metric_tolerances: dict[str, float] = field(default_factory=dict)
    metric_directions: dict[str, ScoreDirection] = field(default_factory=dict)

    def tolerance_for(self, metric_name: str) -> float:
        return self.metric_tolerances.get(metric_name, self.default_tolerance)

    def direction_for(self, metric_name: str) -> ScoreDirection:
        return self.metric_directions.get(metric_name, ScoreDirection.HIGHER_IS_BETTER)


@dataclass(frozen=True, slots=True)
class RegressionResult:
    """Complete regression analysis result."""

    baseline_run_id: str
    current_run_id: str
    baseline_fingerprint: str
    current_fingerprint: str
    fingerprints_compatible: bool
    metric_comparisons: tuple[MetricRegression, ...]
    verdict: RegressionVerdict
    regression_count: int = 0
    error_count: int = 0
    not_comparable_count: int = 0
    reasoning: str = ""


def analyze_regression(
    *,
    baseline_run_id: str,
    current_run_id: str,
    baseline_fingerprint: str,
    current_fingerprint: str,
    baseline_metrics: dict[str, float | None],
    current_metrics: dict[str, float | None],
    config: RegressionConfig | None = None,
) -> RegressionResult:
    """Analyze regression between baseline and current metric results.

    Args:
        baseline_run_id: ID of the baseline run.
        current_run_id: ID of the current run.
        baseline_fingerprint: Fingerprint of baseline evaluation config.
        current_fingerprint: Fingerprint of current evaluation config.
        baseline_metrics: Metric name -> normalized score (or None on error).
        current_metrics: Metric name -> normalized score (or None on error).
        config: Regression tolerance and direction configuration.

    Returns:
        RegressionResult with per-metric analysis and overall verdict.

    """
    cfg = config or RegressionConfig()

    # Check fingerprint compatibility
    fingerprints_compatible = baseline_fingerprint == current_fingerprint

    # Collect all metric names
    all_metric_names = sorted(set(baseline_metrics.keys()) | set(current_metrics.keys()))

    comparisons: list[MetricRegression] = []
    regression_count = 0
    error_count = 0
    not_comparable_count = 0

    for name in all_metric_names:
        b_score = baseline_metrics.get(name)
        c_score = current_metrics.get(name)

        comparison = _analyze_metric(name, b_score, c_score, cfg)
        comparisons.append(comparison)

        if comparison.status == MetricStatus.REGRESSION:
            regression_count += 1
        elif comparison.status == MetricStatus.ERROR:
            error_count += 1
        elif comparison.status == MetricStatus.NOT_COMPARABLE:
            not_comparable_count += 1

    # Determine overall verdict
    verdict = _determine_verdict(
        regression_count=regression_count,
        error_count=error_count,
        fingerprints_compatible=fingerprints_compatible,
        has_metrics=len(comparisons) > 0,
    )

    reasoning = _build_reasoning(
        verdict=verdict,
        regression_count=regression_count,
        error_count=error_count,
        not_comparable_count=not_comparable_count,
        fingerprints_compatible=fingerprints_compatible,
    )

    return RegressionResult(
        baseline_run_id=baseline_run_id,
        current_run_id=current_run_id,
        baseline_fingerprint=baseline_fingerprint,
        current_fingerprint=current_fingerprint,
        fingerprints_compatible=fingerprints_compatible,
        metric_comparisons=tuple(comparisons),
        verdict=verdict,
        regression_count=regression_count,
        error_count=error_count,
        not_comparable_count=not_comparable_count,
        reasoning=reasoning,
    )


def _analyze_metric(
    name: str,
    baseline: float | None,
    current: float | None,
    config: RegressionConfig,
) -> MetricRegression:
    """Analyze a single metric for regression."""
    direction = config.direction_for(name)
    tolerance = config.tolerance_for(name)

    # Missing metrics
    if baseline is None and current is None:
        return MetricRegression(
            metric_name=name,
            baseline_score=None,
            current_score=None,
            delta=0.0,
            direction=direction,
            tolerance=tolerance,
            status=MetricStatus.NOT_COMPARABLE,
            reasoning="Metric missing from both baseline and current",
        )

    if baseline is None:
        return MetricRegression(
            metric_name=name,
            baseline_score=None,
            current_score=current,
            delta=0.0,
            direction=direction,
            tolerance=tolerance,
            status=MetricStatus.ADDED,
            reasoning="Metric not present in baseline; new in current",
        )

    if current is None:
        return MetricRegression(
            metric_name=name,
            baseline_score=baseline,
            current_score=None,
            delta=0.0,
            direction=direction,
            tolerance=tolerance,
            status=MetricStatus.REMOVED,
            reasoning="Metric present in baseline but missing from current",
        )

    # Both scores available — compute degradation
    delta = current - baseline

    if direction == ScoreDirection.HIGHER_IS_BETTER:
        # Degradation is when current < baseline (delta < 0)
        degradation = -delta  # positive means worse
    else:
        # LOWER_IS_BETTER: degradation is when current > baseline (delta > 0)
        degradation = delta

    if degradation <= tolerance:
        status = MetricStatus.PASS
        reasoning = f"Within tolerance ({degradation:.4f} <= {tolerance})"
    elif abs(delta) < 1e-9:
        status = MetricStatus.NO_CHANGE
        reasoning = "Scores are equal"
    else:
        status = MetricStatus.REGRESSION
        direction_label = "higher is better" if direction == ScoreDirection.HIGHER_IS_BETTER else "lower is better"
        reasoning = f"Regression detected ({direction_label}): degradation {degradation:.4f} > tolerance {tolerance}"

    # Check for improvement
    if status == MetricStatus.PASS and degradation < 0:
        status = MetricStatus.IMPROVEMENT
        reasoning = f"Improvement: delta {delta:.4f}"

    return MetricRegression(
        metric_name=name,
        baseline_score=baseline,
        current_score=current,
        delta=delta,
        direction=direction,
        tolerance=tolerance,
        status=status,
        reasoning=reasoning,
    )


def _determine_verdict(
    *,
    regression_count: int,
    error_count: int,
    fingerprints_compatible: bool,
    has_metrics: bool,
) -> RegressionVerdict:
    """Determine overall regression verdict."""
    if not has_metrics:
        return RegressionVerdict.NOT_COMPARABLE

    if not fingerprints_compatible:
        return RegressionVerdict.NOT_COMPARABLE

    if regression_count > 0:
        return RegressionVerdict.FAIL

    if error_count > 0:
        return RegressionVerdict.ERROR

    return RegressionVerdict.PASS


def _build_reasoning(
    *,
    verdict: RegressionVerdict,
    regression_count: int,
    error_count: int,
    not_comparable_count: int,
    fingerprints_compatible: bool,
) -> str:
    """Build human-readable reasoning for the verdict."""
    parts: list[str] = []

    if verdict == RegressionVerdict.FAIL:
        parts.append(f"Regression detected: {regression_count} metric(s) regressed")
    elif verdict == RegressionVerdict.PASS:
        parts.append("All metrics within tolerance")
    elif verdict == RegressionVerdict.NOT_COMPARABLE:
        if not fingerprints_compatible:
            parts.append("Evaluation configurations differ (fingerprint mismatch)")
        else:
            parts.append("No comparable metrics found")
    elif verdict == RegressionVerdict.ERROR:
        parts.append(f"Evaluation errors: {error_count} metric(s) had errors")

    if not_comparable_count > 0:
        parts.append(f"{not_comparable_count} metric(s) not comparable")

    if not fingerprints_compatible:
        parts.append("Fingerprint mismatch — configurations may differ materially")

    return ". ".join(parts) if parts else "No analysis available"
