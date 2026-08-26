"""Tests for model comparison."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.evaluation.reliability.comparison import (
    compare_models,
)
from app.evaluation.replay.domain import (
    ExecutionTrace,
    ItemTrace,
    MetricTrace,
    PromptTrace,
    ProviderTrace,
)


def _make_trace(
    provider: str,
    model: str,
    items: list[dict],
) -> ExecutionTrace:
    """Build a minimal ExecutionTrace for testing."""
    item_traces = []
    for item in items:
        metric_traces = tuple(
            MetricTrace(
                metric_name=m["name"],
                score=m["score"],
                normalized_score=m["norm"],
                cost_usd=m.get("cost", 0.0),
                execution_time_ms=m.get("latency", 0),
            )
            for m in item.get("metrics", [])
        )
        item_traces.append(
            ItemTrace(
                item_index=item["index"],
                prompt_trace=PromptTrace(prompt=item.get("prompt", "test")),
                provider_trace=ProviderTrace(
                    provider_name=provider,
                    model_id=model,
                    tokens_input=item.get("tokens_in", 0),
                    tokens_output=item.get("tokens_out", 0),
                    cost_usd=item.get("cost", 0.0),
                    latency_ms=item.get("latency", 0),
                ),
                metric_traces=metric_traces,
                total_cost_usd=item.get("cost", 0.0),
                total_latency_ms=item.get("latency", 0),
            )
        )

    return ExecutionTrace(
        run_id="test-run",
        provider_name=provider,
        model_id=model,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        status="completed",
        item_traces=tuple(item_traces),
        total_cost_usd=sum(i.get("cost", 0.0) for i in items),
        total_tokens_input=sum(i.get("tokens_in", 0) for i in items),
        total_tokens_output=sum(i.get("tokens_out", 0) for i in items),
    )


class TestModelComparison:
    def test_same_models_tie(self) -> None:
        items = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.8, "norm": 0.8},
                ],
            }
        ]
        trace_a = _make_trace("openai", "gpt-4", items)
        trace_b = _make_trace("openai", "gpt-4", items)

        result = compare_models(trace_a, trace_b)
        assert result.winner == "tie"
        assert result.a_better_count == 0
        assert result.b_better_count == 0

    def test_model_b_better(self) -> None:
        items_a = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.5, "norm": 0.5},
                ],
            }
        ]
        items_b = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.9, "norm": 0.9},
                ],
            }
        ]
        trace_a = _make_trace("openai", "gpt-3.5", items_a)
        trace_b = _make_trace("openai", "gpt-4", items_b)

        result = compare_models(trace_a, trace_b, model_a_name="gpt-3.5", model_b_name="gpt-4")
        assert result.winner == "model_b"
        assert result.b_better_count == 1
        assert result.a_better_count == 0

    def test_model_a_better(self) -> None:
        items_a = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.9, "norm": 0.9},
                ],
            }
        ]
        items_b = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.5, "norm": 0.5},
                ],
            }
        ]
        trace_a = _make_trace("openai", "gpt-4", items_a)
        trace_b = _make_trace("openai", "gpt-3.5", items_b)

        result = compare_models(trace_a, trace_b, model_a_name="gpt-4", model_b_name="gpt-3.5")
        assert result.winner == "model_a"

    def test_multiple_metrics(self) -> None:
        items_a = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.9, "norm": 0.9},
                    {"name": "coherence", "score": 0.4, "norm": 0.4},
                ],
            }
        ]
        items_b = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.5, "norm": 0.5},
                    {"name": "coherence", "score": 0.9, "norm": 0.9},
                ],
            }
        ]
        trace_a = _make_trace("openai", "gpt-4", items_a)
        trace_b = _make_trace("openai", "gpt-4", items_b)

        result = compare_models(trace_a, trace_b)
        assert result.tie_count == 1 or (result.a_better_count == 1 and result.b_better_count == 1)

    def test_cost_difference(self) -> None:
        items_a = [{"index": 0, "prompt": "test", "cost": 0.01, "metrics": []}]
        items_b = [{"index": 0, "prompt": "test", "cost": 0.05, "metrics": []}]

        trace_a = _make_trace("openai", "gpt-4", items_a)
        trace_b = _make_trace("openai", "gpt-4", items_b)

        result = compare_models(trace_a, trace_b)
        assert result.total_cost_difference == pytest.approx(0.04, abs=1e-6)

    def test_token_difference(self) -> None:
        items_a = [
            {"index": 0, "prompt": "test", "tokens_in": 100, "tokens_out": 50, "metrics": []}
        ]
        items_b = [
            {"index": 0, "prompt": "test", "tokens_in": 200, "tokens_out": 100, "metrics": []}
        ]

        trace_a = _make_trace("openai", "gpt-4", items_a)
        trace_b = _make_trace("openai", "gpt-4", items_b)

        result = compare_models(trace_a, trace_b)
        assert result.a_total_tokens == 150
        assert result.b_total_tokens == 300

    def test_metric_comparisons_preserved(self) -> None:
        items_a = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.8, "norm": 0.8},
                ],
            }
        ]
        items_b = [
            {
                "index": 0,
                "prompt": "test",
                "metrics": [
                    {"name": "correctness", "score": 0.9, "norm": 0.9},
                ],
            }
        ]
        trace_a = _make_trace("openai", "gpt-4", items_a)
        trace_b = _make_trace("openai", "gpt-4", items_b)

        result = compare_models(trace_a, trace_b)
        assert len(result.metric_comparisons) == 1
        mc = result.metric_comparisons[0]
        assert mc.metric_name == "correctness"
        assert mc.model_a_score == pytest.approx(0.8)
        assert mc.model_b_score == pytest.approx(0.9)
