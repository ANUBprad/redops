"""Metric invariant tests.

Verifies that every metric maintains mathematical invariants:
- normalized_score in [0, 1]
- no NaN, no infinity
- correct directionality
- explicit error behavior for missing inputs
- malformed inputs do not silently produce success
"""

from __future__ import annotations

import asyncio
import math

import pytest

from app.evaluation.metrics.domain import MetricInput, MetricResult
from app.evaluation.metrics.implementations import ALL_METRICS
from tests.evaluation.metrics.test_score_contract import (
    _canonical_input,
    _failing_input,
)


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _evaluate_metric(metric_cls: type, input_data: MetricInput) -> MetricResult:
    """Evaluate a metric synchronously."""
    return _run(metric_cls().evaluate(input_data))


class TestNormalizedScoreRange:
    """Every successful result must have normalized_score in [0.0, 1.0]."""

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_no_nan(self, metric_cls: type) -> None:
        input_data = _canonical_input(metric_cls().definition().name)
        if input_data is None:
            pytest.skip(f"no canonical input for {metric_cls().definition().name}")

        result = _evaluate_metric(metric_cls, input_data)
        assert not math.isnan(result.normalized_score), (
            f"{metric_cls().definition().name} returned NaN normalized_score"
        )

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_no_infinity(self, metric_cls: type) -> None:
        input_data = _canonical_input(metric_cls().definition().name)
        if input_data is None:
            pytest.skip(f"no canonical input for {metric_cls().definition().name}")

        result = _evaluate_metric(metric_cls, input_data)
        assert not math.isinf(result.normalized_score), (
            f"{metric_cls().definition().name} returned inf normalized_score"
        )

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_normalized_in_unit_interval(self, metric_cls: type) -> None:
        input_data = _canonical_input(metric_cls().definition().name)
        if input_data is None:
            pytest.skip(f"no canonical input for {metric_cls().definition().name}")

        result = _evaluate_metric(metric_cls, input_data)
        if result.is_success:
            assert 0.0 <= result.normalized_score <= 1.0, (
                f"{metric_cls().definition().name} normalized_score "
                f"{result.normalized_score} not in [0, 1]"
            )


class TestDirectionality:
    """Metrics must declare consistent directionality."""

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_cost_metric_direction(self, metric_cls: type) -> None:
        defn = metric_cls().definition()
        if defn.name == "cost":
            assert defn.direction.value == "higher_is_better"

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_latency_metric_direction(self, metric_cls: type) -> None:
        defn = metric_cls().definition()
        if defn.name == "latency":
            assert defn.direction.value == "higher_is_better"


class TestErrorBehavior:
    """Missing or malformed inputs must produce explicit errors, not silent zeros."""

    @pytest.mark.parametrize("metric_cls", ALL_METRICS)
    def test_missing_inputs_no_silent_zero(self, metric_cls: type) -> None:
        defn = metric_cls().definition()
        failing = _failing_input(defn.name)
        result = _evaluate_metric(metric_cls, failing)

        assert not result.is_success, f"{defn.name} silently succeeded on invalid input"
        assert result.error is not None
        assert result.normalized_score == 0.0


class TestMalformedInputs:
    """Malformed inputs must not silently produce success."""

    def test_json_validity_rejects_non_json(self) -> None:
        from app.evaluation.metrics.implementations.json_validity_metric import (
            JsonValidityMetric,
        )

        result = _evaluate_metric(JsonValidityMetric, MetricInput(response="not json at all"))
        assert result.is_success
        assert result.normalized_score == 0.0

    def test_regex_validation_no_pattern(self) -> None:
        from app.evaluation.metrics.implementations.regex_validation_metric import (
            RegexValidationMetric,
        )

        result = _evaluate_metric(RegexValidationMetric, MetricInput(response="hello"))
        assert not result.is_success

    def test_schema_validation_wrong_schema(self) -> None:
        from app.evaluation.metrics.implementations.schema_validation_metric import (
            SchemaValidationMetric,
        )

        result = _evaluate_metric(
            SchemaValidationMetric,
            MetricInput(
                response='{"a": 1}',
                metadata={"schema": {"type": "object", "required": ["b"]}},
            ),
        )
        assert result.is_success
        assert result.normalized_score == 0.0

    def test_response_length_empty(self) -> None:
        from app.evaluation.metrics.implementations.response_length_metric import (
            ResponseLengthMetric,
        )

        result = _evaluate_metric(ResponseLengthMetric, MetricInput(response=""))
        assert not result.is_success

    def test_token_usage_missing_metadata(self) -> None:
        from app.evaluation.metrics.implementations.token_usage_metric import TokenUsageMetric

        result = _evaluate_metric(TokenUsageMetric, MetricInput(metadata={}))
        assert not result.is_success

    def test_cost_missing_metadata(self) -> None:
        from app.evaluation.metrics.implementations.cost_metric import CostMetric

        result = _evaluate_metric(CostMetric, MetricInput(metadata={}))
        assert not result.is_success

    def test_latency_missing_metadata(self) -> None:
        from app.evaluation.metrics.implementations.latency_metric import LatencyMetric

        result = _evaluate_metric(LatencyMetric, MetricInput(metadata={}))
        assert not result.is_success
