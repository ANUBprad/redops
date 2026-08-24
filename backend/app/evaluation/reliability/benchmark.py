"""Deterministic evaluation benchmark runner.

Runs golden evaluation fixtures against deterministic metric
implementations and checks results against expected baselines.
Detects metric score regressions, changed directionality, and
unexpected errors.

Usable from pytest or as a standalone module:

    python -m app.evaluation.reliability.benchmark
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.evaluation.metrics.domain import (
    MetricInput,
    MetricResult,
)


class MetricEvaluator(Protocol):
    """Protocol for objects that can evaluate a single metric."""

    async def evaluate_single(self, metric_name: str, input_data: MetricInput) -> MetricResult: ...


@dataclass(frozen=True, slots=True)
class GoldenFixture:
    """A single golden benchmark case with expected metric outcomes."""

    key: str
    description: str
    input: MetricInput
    expected_results: dict[str, GoldenExpectation] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GoldenExpectation:
    """Expected outcome for a metric in a golden fixture."""

    min_score: float = 0.0
    max_score: float = 1.0
    min_normalized: float = 0.0
    max_normalized: float = 1.0
    expect_success: bool = True
    exact_score: float | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Result of running a single golden fixture."""

    fixture_key: str
    metric_name: str
    passed: bool
    actual_score: float = 0.0
    actual_normalized: float = 0.0
    expected_min: float = 0.0
    expected_max: float = 1.0
    error: str | None = None
    details: str = ""


@dataclass
class BenchmarkReport:
    """Aggregated benchmark results."""

    results: list[BenchmarkResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0

    def add(self, result: BenchmarkResult) -> None:
        """Add a result and update counters."""
        self.results.append(result)
        self.total += 1
        if result.passed:
            self.passed += 1
        else:
            self.failed += 1

    @property
    def success(self) -> bool:
        """Return True if all benchmarks passed."""
        return self.failed == 0

    def failures(self) -> list[BenchmarkResult]:
        """Return only failed results."""
        return [r for r in self.results if not r.passed]

    def to_dict(self) -> dict[str, object]:
        """Serialize to dictionary."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "success": self.success,
            "results": [
                {
                    "fixture": r.fixture_key,
                    "metric": r.metric_name,
                    "passed": r.passed,
                    "actual_score": r.actual_score,
                    "actual_normalized": r.actual_normalized,
                    "expected_range": [r.expected_min, r.expected_max],
                    "error": r.error,
                    "details": r.details,
                }
                for r in self.results
            ],
        }


async def run_benchmark(
    fixtures: list[GoldenFixture],
    metric_engine: MetricEvaluator,
    *,
    strict: bool = True,
) -> BenchmarkReport:
    """Run golden fixtures against the metric engine.

    Args:
        fixtures: Golden benchmark cases.
        metric_engine: MetricEngine instance with metrics registered.
        strict: If True, any failure makes the report unsuccessful.

    Returns:
        BenchmarkReport with pass/fail for each fixture-metric pair.

    """
    report = BenchmarkReport()

    for fixture in fixtures:
        for metric_name, expectation in fixture.expected_results.items():
            try:
                result = await metric_engine.evaluate_single(metric_name, fixture.input)
                passed = _check_expectation(result, expectation)
                report.add(
                    BenchmarkResult(
                        fixture_key=fixture.key,
                        metric_name=metric_name,
                        passed=passed,
                        actual_score=result.score,
                        actual_normalized=result.normalized_score,
                        expected_min=expectation.min_normalized,
                        expected_max=expectation.max_normalized,
                        error=result.error,
                        details=(
                            f"score={result.score:.4f} normalized={result.normalized_score:.4f}"
                        ),
                    )
                )
            except Exception as exc:
                report.add(
                    BenchmarkResult(
                        fixture_key=fixture.key,
                        metric_name=metric_name,
                        passed=False,
                        error=str(exc),
                        details=f"exception: {exc}",
                    )
                )

    return report


def _check_expectation(result: MetricResult, expectation: GoldenExpectation) -> bool:
    """Check if a result matches an expectation."""
    if expectation.exact_score is not None:
        if abs(result.normalized_score - expectation.exact_score) > 0.001:
            return False

    if not expectation.expect_success:
        return not result.is_success

    if result.error is not None:
        return False

    return expectation.min_normalized <= result.normalized_score <= expectation.max_normalized
