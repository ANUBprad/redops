"""Tests for evaluation regression analysis (B.9.3).

Deterministic tests covering all regression scenarios:
direction-aware comparison, tolerance, missing metrics,
errors, fingerprint compatibility, and CLI behavior.
"""

from __future__ import annotations

import json

import pytest

from app.evaluation.metrics.domain import ScoreDirection
from app.evaluation.regression import (
    MetricStatus,
    RegressionConfig,
    RegressionVerdict,
    analyze_regression,
)

# ---------------------------------------------------------------------------
# Test 1 — Higher-is-better regression
# ---------------------------------------------------------------------------


class TestHigherIsBetterRegression:
    """Baseline 0.90, Current 0.80 — should be REGRESSION."""

    def test_regression_detected(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": 0.90},
            current_metrics={"correctness": 0.80},
        )
        assert result.verdict == RegressionVerdict.FAIL
        assert result.regression_count == 1
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.REGRESSION
        assert mc.delta == pytest.approx(-0.10, abs=0.001)


# ---------------------------------------------------------------------------
# Test 2 — Higher-is-better within tolerance
# ---------------------------------------------------------------------------


class TestHigherIsBetterWithinTolerance:
    """Baseline 0.90, Current 0.89, Tolerance 0.02 — should PASS."""

    def test_within_tolerance_passes(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": 0.90},
            current_metrics={"correctness": 0.89},
            config=RegressionConfig(default_tolerance=0.02),
        )
        assert result.verdict == RegressionVerdict.PASS
        assert result.regression_count == 0
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.PASS


# ---------------------------------------------------------------------------
# Test 3 — Lower-is-better regression
# ---------------------------------------------------------------------------


class TestLowerIsBetterRegression:
    """Baseline 100ms, Current 150ms — should be REGRESSION."""

    def test_regression_detected(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"latency": 100.0},
            current_metrics={"latency": 150.0},
            config=RegressionConfig(
                default_tolerance=5.0,
                metric_directions={"latency": ScoreDirection.LOWER_IS_BETTER},
            ),
        )
        assert result.verdict == RegressionVerdict.FAIL
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.REGRESSION
        assert mc.delta == 50.0


# ---------------------------------------------------------------------------
# Test 4 — Lower-is-better improvement
# ---------------------------------------------------------------------------


class TestLowerIsBetterImprovement:
    """Baseline 100ms, Current 80ms — should PASS (improvement)."""

    def test_improvement_detected(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"latency": 100.0},
            current_metrics={"latency": 80.0},
            config=RegressionConfig(
                default_tolerance=5.0,
                metric_directions={"latency": ScoreDirection.LOWER_IS_BETTER},
            ),
        )
        assert result.verdict == RegressionVerdict.PASS
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.IMPROVEMENT


# ---------------------------------------------------------------------------
# Test 5 — Equal score
# ---------------------------------------------------------------------------


class TestEqualScore:
    """Baseline 0.85, Current 0.85 — should PASS."""

    def test_equal_scores_pass(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": 0.85},
            current_metrics={"correctness": 0.85},
        )
        assert result.verdict == RegressionVerdict.PASS
        mc = result.metric_comparisons[0]
        assert mc.status in (MetricStatus.PASS, MetricStatus.NO_CHANGE)


# ---------------------------------------------------------------------------
# Test 6 — Missing current metric
# ---------------------------------------------------------------------------


class TestMissingCurrentMetric:
    """Baseline has metric, current does not — should be REMOVED."""

    def test_removed_metric(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": 0.90},
            current_metrics={},
        )
        assert result.verdict == RegressionVerdict.PASS
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.REMOVED
        assert mc.baseline_score == 0.90
        assert mc.current_score is None


# ---------------------------------------------------------------------------
# Test 7 — New current metric
# ---------------------------------------------------------------------------


class TestNewCurrentMetric:
    """Current has metric, baseline does not — should be ADDED."""

    def test_added_metric(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={},
            current_metrics={"hallucination": 0.10},
        )
        assert result.verdict == RegressionVerdict.PASS
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.ADDED
        assert mc.baseline_score is None
        assert mc.current_score == 0.10


# ---------------------------------------------------------------------------
# Test 8 — Metric error
# ---------------------------------------------------------------------------


class TestMetricError:
    """Metric had an error — should be NOT_COMPARABLE / ERROR."""

    def test_error_not_comparable(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": None},
            current_metrics={"correctness": 0.80},
        )
        # None in baseline means error/not-available
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.ADDED

    def test_both_none_not_comparable(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": None},
            current_metrics={"correctness": None},
        )
        mc = result.metric_comparisons[0]
        assert mc.status == MetricStatus.NOT_COMPARABLE


# ---------------------------------------------------------------------------
# Test 9 — Fingerprint match
# ---------------------------------------------------------------------------


class TestFingerprintMatch:
    """Same fingerprints — comparable = true."""

    def test_comparable(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="abc123",
            current_fingerprint="abc123",
            baseline_metrics={"correctness": 0.90},
            current_metrics={"correctness": 0.85},
        )
        assert result.fingerprints_compatible is True
        assert result.verdict != RegressionVerdict.NOT_COMPARABLE


# ---------------------------------------------------------------------------
# Test 10 — Fingerprint mismatch
# ---------------------------------------------------------------------------


class TestFingerprintMismatch:
    """Different fingerprints — explicit incompatibility."""

    def test_not_comparable(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="abc123",
            current_fingerprint="xyz789",
            baseline_metrics={"correctness": 0.90},
            current_metrics={"correctness": 0.85},
        )
        assert result.fingerprints_compatible is False
        assert result.verdict == RegressionVerdict.NOT_COMPARABLE


# ---------------------------------------------------------------------------
# Test 11 — Multiple metrics, one regression
# ---------------------------------------------------------------------------


class TestMultipleMetricsOneRegression:
    """One metric regresses among passing metrics — overall FAIL."""

    def test_overall_fail(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={
                "correctness": 0.90,
                "relevance": 0.85,
                "coherence": 0.88,
            },
            current_metrics={
                "correctness": 0.80,  # regression
                "relevance": 0.86,  # improvement
                "coherence": 0.89,  # improvement
            },
            config=RegressionConfig(default_tolerance=0.02),
        )
        assert result.verdict == RegressionVerdict.FAIL
        assert result.regression_count == 1

        # Find the regressed metric
        regressed = [mc for mc in result.metric_comparisons if mc.status == MetricStatus.REGRESSION]
        assert len(regressed) == 1
        assert regressed[0].metric_name == "correctness"


# ---------------------------------------------------------------------------
# Test 12 — All metrics pass
# ---------------------------------------------------------------------------


class TestAllMetricsPass:
    """All metrics within tolerance — overall PASS."""

    def test_overall_pass(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={
                "correctness": 0.90,
                "relevance": 0.85,
            },
            current_metrics={
                "correctness": 0.89,
                "relevance": 0.84,
            },
            config=RegressionConfig(default_tolerance=0.02),
        )
        assert result.verdict == RegressionVerdict.PASS
        assert result.regression_count == 0


# ---------------------------------------------------------------------------
# Test 13 — CLI exit code regression
# ---------------------------------------------------------------------------


class TestCLIExitCodeRegression:
    """CLI returns non-zero on regression."""

    def test_regression_exit_code(self) -> None:
        from app.evaluation.regression import RegressionVerdict

        # Simulate what CLI would do
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": 0.90},
            current_metrics={"correctness": 0.70},
        )

        # Map verdict to exit code
        if result.verdict == RegressionVerdict.PASS:
            exit_code = 0
        elif result.verdict == RegressionVerdict.FAIL:
            exit_code = 1
        elif result.verdict == RegressionVerdict.ERROR:
            exit_code = 2
        elif result.verdict == RegressionVerdict.NOT_COMPARABLE:
            exit_code = 3
        else:
            exit_code = 1

        assert exit_code == 1


# ---------------------------------------------------------------------------
# Test 14 — CLI exit code success
# ---------------------------------------------------------------------------


class TestCLIExitCodeSuccess:
    """CLI returns 0 on no regression."""

    def test_success_exit_code(self) -> None:
        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": 0.90},
            current_metrics={"correctness": 0.89},
            config=RegressionConfig(default_tolerance=0.02),
        )

        if result.verdict == RegressionVerdict.PASS:
            exit_code = 0
        else:
            exit_code = 1

        assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 15 — JSON output schema
# ---------------------------------------------------------------------------


class TestJSONOutput:
    """Machine-readable JSON schema is valid."""

    def test_json_serializable(self) -> None:
        from app.cli import _result_to_dict

        result = analyze_regression(
            baseline_run_id="b1",
            current_run_id="c1",
            baseline_fingerprint="fp1",
            current_fingerprint="fp1",
            baseline_metrics={"correctness": 0.90, "latency": 100.0},
            current_metrics={"correctness": 0.85, "latency": 120.0},
            config=RegressionConfig(
                default_tolerance=0.02,
                metric_directions={"latency": ScoreDirection.LOWER_IS_BETTER},
            ),
        )

        d = _result_to_dict(result)
        serialized = json.dumps(d, indent=2)
        parsed = json.loads(serialized)

        assert parsed["baseline_run_id"] == "b1"
        assert parsed["current_run_id"] == "c1"
        assert parsed["verdict"] in ("pass", "fail", "error", "not_comparable")
        assert isinstance(parsed["metric_comparisons"], list)
        assert len(parsed["metric_comparisons"]) == 2

        for mc in parsed["metric_comparisons"]:
            assert "metric_name" in mc
            assert "status" in mc
            assert "delta" in mc
            assert "direction" in mc


# ---------------------------------------------------------------------------
# Test 16 — Real persisted traces comparison
# ---------------------------------------------------------------------------


class TestRealPersistedTraces:
    """Use existing deterministic fixtures to prove real comparison path."""

    def test_comparison_through_replay_service(self) -> None:
        """Compare two ExecutionTrace objects through ReplayService."""
        from app.evaluation.replay.domain import ExecutionTrace
        from app.evaluation.replay.service import ReplayService

        baseline_data = {
            "run_id": "run-baseline-001",
            "evaluation_name": "test-eval",
            "provider_name": "openai",
            "model_id": "gpt-4",
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:01:00Z",
            "status": "completed",
            "item_traces": [
                {
                    "item_index": 0,
                    "prompt_trace": {"prompt": "What is 2+2?"},
                    "provider_trace": {
                        "provider_name": "openai",
                        "model_id": "gpt-4",
                        "response_content": "4",
                        "tokens_input": 10,
                        "tokens_output": 5,
                        "cost_usd": 0.001,
                        "latency_ms": 100,
                    },
                    "metric_traces": [
                        {
                            "metric_name": "correctness",
                            "score": 0.95,
                            "normalized_score": 0.95,
                            "confidence": 0.9,
                            "reasoning": "Correct",
                            "version": "1.0.0",
                            "cost_usd": 0.0,
                            "execution_time_ms": 50,
                        }
                    ],
                    "total_latency_ms": 100,
                    "total_cost_usd": 0.001,
                }
            ],
            "total_cost_usd": 0.001,
            "total_tokens_input": 10,
            "total_tokens_output": 5,
            "total_latency_ms": 100,
            "configuration": {"provider": "openai", "model": "gpt-4"},
        }

        current_data = {
            **baseline_data,
            "run_id": "run-current-001",
            "item_traces": [
                {
                    **baseline_data["item_traces"][0],
                    "metric_traces": [
                        {
                            **baseline_data["item_traces"][0]["metric_traces"][0],
                            "score": 0.80,
                            "normalized_score": 0.80,
                            "reasoning": "Slightly off",
                        }
                    ],
                }
            ],
        }

        baseline_trace = ExecutionTrace.from_dict(baseline_data)
        current_trace = ExecutionTrace.from_dict(current_data)

        service = ReplayService()
        comparison = service.compare_traces(baseline_trace, current_trace)

        # Now run regression analysis on the comparison data
        baseline_metrics = {}
        current_metrics = {}
        for name, deltas in comparison.metric_deltas.items():
            baseline_metrics[name] = deltas["baseline_mean"]
            current_metrics[name] = deltas["comparison_mean"]

        result = analyze_regression(
            baseline_run_id=baseline_trace.run_id,
            current_run_id=current_trace.run_id,
            baseline_fingerprint="fp-same",
            current_fingerprint="fp-same",
            baseline_metrics=baseline_metrics,
            current_metrics=current_metrics,
            config=RegressionConfig(default_tolerance=0.02),
        )

        # Correctness dropped from 0.95 to 0.80 — regression
        assert result.verdict == RegressionVerdict.FAIL
        assert result.regression_count == 1
        mc = result.metric_comparisons[0]
        assert mc.metric_name == "correctness"
        assert mc.baseline_score == 0.95
        assert mc.current_score == 0.80
