"""Metric exception semantics (P4-C).

A metric that raises must never silently become a success, a real
zero, or missing evidence. These tests pin the explicit error
semantics of the engine and aggregation for both mixed and
all-failed runs using deterministic fake metrics.
"""

from __future__ import annotations

import pytest

from app.evaluation.metrics.domain import (
    Metric,
    MetricAggregation,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.engine import MetricEngine


class _BoomMetric(Metric):
    """Metric that always raises during evaluation."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="boom",
            display_name="Boom",
            description="Raises always",
            category=MetricCategory.QUALITY,
            scale=MetricScale.BINARY,
            version="9.9.9",
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        raise RuntimeError("boom-message")


class _OkMetric(Metric):
    """Metric that always succeeds deterministically."""

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="ok",
            display_name="Ok",
            description="Succeeds always",
            category=MetricCategory.QUALITY,
            scale=MetricScale.BINARY,
            version="2.0.0",
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        return MetricResult(
            metric_name="ok",
            score=0.9,
            normalized_score=0.9,
            version="2.0.0",
        )


def _engine() -> MetricEngine:
    engine = MetricEngine()
    engine.register(_BoomMetric())
    engine.register(_OkMetric())
    return engine


def _input() -> MetricInput:
    return MetricInput(
        prompt="p",
        response="r",
        metadata={
            "run_id": "run-abc",
            "item_id": "item-1",
            "_judge_provider_name": "openai",
            "_judge_model": "gpt-4o",
        },
    )


class TestMetricExceptionSemantics:
    """Exceptions become explicit error MetricResults, never success/zero."""

    @pytest.mark.asyncio
    async def test_exception_yields_explicit_error_result(self) -> None:
        """A raising metric produces an error result, not a success or a raise."""
        engine = _engine()
        results = await engine.evaluate_batch(("ok", "boom"), _input())

        ok, boom = results
        assert ok.is_success is True
        assert ok.score == 0.9
        assert ok.version == "2.0.0"

        assert boom.is_success is False
        assert boom.passed_against(0.5) is None
        assert boom.error is not None
        assert "RuntimeError" in boom.error
        assert "boom-message" in boom.error
        assert boom.score == 0.0
        assert boom.normalized_score == 0.0

    @pytest.mark.asyncio
    async def test_error_result_preserves_available_diagnostics(self) -> None:
        """Version, run/item identity, and judge identifiers are preserved."""
        engine = _engine()
        result = (await engine.evaluate_batch(("boom",), _input()))[0]

        assert result.version == "9.9.9"
        assert result.metadata["run_id"] == "run-abc"
        assert result.metadata["item_id"] == "item-1"
        assert result.metadata["_judge_provider_name"] == "openai"
        assert result.metadata["_judge_model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_multiple_failing_metrics_behave_consistently(self) -> None:
        """Two raising evaluations produce the same explicit error shape."""
        engine = _engine()
        results = await engine.evaluate_batch(("boom", "boom"), _input())
        assert len(results) == 2
        for result in results:
            assert result.is_success is False
            assert result.error is not None
            assert result.version == "9.9.9"


class TestAggregationFailureSemantics:
    """Aggregation excludes failed results instead of scoring them zero."""

    def test_mixed_success_failure_excludes_errors(self) -> None:
        """Failed results are counted but their placeholder zero is excluded."""
        results = (
            MetricResult(metric_name="m", score=0.8, normalized_score=0.8, version="1.0.0"),
            MetricResult(
                metric_name="m",
                score=0.0,
                normalized_score=0.0,
                version="1.0.0",
                error="RuntimeError: boom",
            ),
        )
        agg = MetricAggregation.from_results("m", results)

        assert agg.success_count == 1
        assert agg.error_count == 1
        assert agg.item_count == 2
        assert agg.mean == 0.8
        assert agg.min_score == 0.8
        assert agg.max_score == 0.8
        assert abs(agg.success_rate - 0.5) < 1e-9

    def test_all_fail_is_explicit(self) -> None:
        """All-failed aggregation reports zero successes, never a real score."""
        results = (
            MetricResult(
                metric_name="m",
                score=0.0,
                normalized_score=0.0,
                version="1.0.0",
                error="RuntimeError: a",
            ),
            MetricResult(
                metric_name="m",
                score=0.0,
                normalized_score=0.0,
                version="1.0.0",
                error="RuntimeError: b",
            ),
        )
        agg = MetricAggregation.from_results("m", results)

        assert agg.item_count == 2
        assert agg.success_count == 0
        assert agg.error_count == 2
        assert agg.success_rate == 0.0
        assert agg.mean == 0.0
