"""Tests for the benchmark runner."""

from __future__ import annotations

from app.evaluation.metrics.domain import MetricResult
from app.evaluation.reliability.benchmark import (
    BenchmarkReport,
    BenchmarkResult,
    GoldenExpectation,
    _check_expectation,
)


class TestGoldenExpectation:
    def test_expectation_in_range(self) -> None:
        result = MetricResult(metric_name="m", score=0.8, normalized_score=0.8)
        exp = GoldenExpectation(min_normalized=0.5, max_normalized=1.0)
        assert _check_expectation(result, exp)

    def test_expectation_out_of_range(self) -> None:
        result = MetricResult(metric_name="m", score=0.3, normalized_score=0.3)
        exp = GoldenExpectation(min_normalized=0.5, max_normalized=1.0)
        assert not _check_expectation(result, exp)

    def test_exact_score_match(self) -> None:
        result = MetricResult(metric_name="m", score=0.75, normalized_score=0.75)
        exp = GoldenExpectation(exact_score=0.75)
        assert _check_expectation(result, exp)

    def test_exact_score_mismatch(self) -> None:
        result = MetricResult(metric_name="m", score=0.75, normalized_score=0.75)
        exp = GoldenExpectation(exact_score=0.80)
        assert not _check_expectation(result, exp)

    def test_expect_error(self) -> None:
        result = MetricResult(metric_name="m", score=0.0, normalized_score=0.0, error="fail")
        exp = GoldenExpectation(expect_success=False)
        assert _check_expectation(result, exp)

    def test_expect_success_but_error(self) -> None:
        result = MetricResult(metric_name="m", score=0.0, normalized_score=0.0, error="fail")
        exp = GoldenExpectation(expect_success=True)
        assert not _check_expectation(result, exp)


class TestBenchmarkReport:
    def test_empty_report(self) -> None:
        report = BenchmarkReport()
        assert report.total == 0
        assert report.success

    def test_all_pass(self) -> None:
        report = BenchmarkReport()
        report.add(BenchmarkResult(fixture_key="f1", metric_name="m1", passed=True))
        assert report.total == 1
        assert report.passed == 1
        assert report.failed == 0
        assert report.success

    def test_one_fail(self) -> None:
        report = BenchmarkReport()
        report.add(BenchmarkResult(fixture_key="f1", metric_name="m1", passed=True))
        report.add(BenchmarkResult(fixture_key="f2", metric_name="m2", passed=False))
        assert report.total == 2
        assert report.failed == 1
        assert not report.success

    def test_failures_list(self) -> None:
        report = BenchmarkReport()
        report.add(BenchmarkResult(fixture_key="f1", metric_name="m1", passed=True))
        fail = BenchmarkResult(fixture_key="f2", metric_name="m2", passed=False)
        report.add(fail)
        assert len(report.failures()) == 1
        assert report.failures()[0].fixture_key == "f2"

    def test_to_dict(self) -> None:
        report = BenchmarkReport()
        report.add(
            BenchmarkResult(fixture_key="f1", metric_name="m1", passed=True, actual_score=0.8)
        )
        d = report.to_dict()
        assert d["total"] == 1
        assert d["passed"] == 1
        assert d["success"]
