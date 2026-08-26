"""Tests for replay/trace consistency.

Verifies that replay traces accurately represent the execution and
that serialization/deserialization preserves all data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.evaluation.replay.domain import (
    ExecutionTrace,
    ItemTrace,
    MetricTrace,
    PromptTrace,
    ProviderTrace,
    TraceEvent,
    TraceEventType,
)
from app.evaluation.replay.service import ReplayService


def _sample_trace() -> ExecutionTrace:
    """Build a sample execution trace for testing."""
    now = datetime.now(UTC)
    return ExecutionTrace(
        run_id="run-123",
        evaluation_name="test-eval",
        provider_name="openai",
        model_id="gpt-4",
        started_at=now,
        completed_at=now,
        status="completed",
        events=(
            TraceEvent(
                event_type=TraceEventType.RUN_STARTED,
                timestamp=now,
                sequence=1,
            ),
            TraceEvent(
                event_type=TraceEventType.ITEM_COMPLETED,
                timestamp=now,
                sequence=2,
            ),
        ),
        item_traces=(
            ItemTrace(
                item_index=0,
                prompt_trace=PromptTrace(prompt="What is 2+2?", reference="4"),
                provider_trace=ProviderTrace(
                    provider_name="openai",
                    model_id="gpt-4",
                    response_content="4",
                    tokens_input=10,
                    tokens_output=5,
                    cost_usd=0.001,
                    latency_ms=100,
                ),
                metric_traces=(
                    MetricTrace(
                        metric_name="correctness",
                        score=0.95,
                        normalized_score=0.95,
                        confidence=0.9,
                        reasoning="Correct answer",
                        version="1.0.0",
                        cost_usd=0.001,
                        execution_time_ms=50,
                        judge_model="gpt-4",
                    ),
                ),
                total_latency_ms=150,
                total_cost_usd=0.002,
            ),
        ),
        total_cost_usd=0.002,
        total_tokens_input=10,
        total_tokens_output=5,
        total_latency_ms=150,
        configuration={"metrics": ["correctness"]},
    )


class TestTraceSerialization:
    def test_to_dict_roundtrip(self) -> None:
        trace = _sample_trace()
        d = trace.to_dict()
        restored = ExecutionTrace.from_dict(d)

        assert restored.run_id == trace.run_id
        assert restored.evaluation_name == trace.evaluation_name
        assert restored.provider_name == trace.provider_name
        assert restored.model_id == trace.model_id
        assert restored.status == trace.status
        assert len(restored.item_traces) == len(trace.item_traces)
        assert len(restored.events) == len(trace.events)

    def test_item_trace_preserved(self) -> None:
        trace = _sample_trace()
        d = trace.to_dict()
        restored = ExecutionTrace.from_dict(d)

        item = restored.item_traces[0]
        assert item.item_index == 0
        assert item.prompt_trace.prompt == "What is 2+2?"
        assert item.provider_trace is not None
        assert item.provider_trace.response_content == "4"
        assert item.provider_trace.tokens_input == 10
        assert item.provider_trace.cost_usd == 0.001

    def test_metric_trace_preserved(self) -> None:
        trace = _sample_trace()
        d = trace.to_dict()
        restored = ExecutionTrace.from_dict(d)

        mt = restored.item_traces[0].metric_traces[0]
        assert mt.metric_name == "correctness"
        assert mt.score == 0.95
        assert mt.normalized_score == 0.95
        assert mt.confidence == 0.9
        assert mt.judge_model == "gpt-4"
        assert mt.version == "1.0.0"

    def test_totals_preserved(self) -> None:
        trace = _sample_trace()
        d = trace.to_dict()
        restored = ExecutionTrace.from_dict(d)

        assert restored.total_cost_usd == 0.002
        assert restored.total_tokens_input == 10
        assert restored.total_tokens_output == 5
        assert restored.total_latency_ms == 150

    def test_empty_trace(self) -> None:
        trace = ExecutionTrace(run_id="empty")
        d = trace.to_dict()
        restored = ExecutionTrace.from_dict(d)
        assert restored.run_id == "empty"
        assert len(restored.item_traces) == 0
        assert len(restored.events) == 0


class TestTraceProperties:
    def test_item_count(self) -> None:
        trace = _sample_trace()
        assert trace.item_count == 1

    def test_success_count(self) -> None:
        trace = _sample_trace()
        assert trace.success_count == 1
        assert trace.failure_count == 0

    def test_failure_count(self) -> None:
        trace = ExecutionTrace(
            run_id="r",
            item_traces=(
                ItemTrace(
                    item_index=0,
                    prompt_trace=PromptTrace(prompt="x"),
                    error="fail",
                ),
            ),
        )
        assert trace.failure_count == 1
        assert trace.success_count == 0

    def test_get_item(self) -> None:
        trace = _sample_trace()
        item = trace.get_item(0)
        assert item is not None
        assert trace.get_item(99) is None

    def test_get_events_by_type(self) -> None:
        trace = _sample_trace()
        events = trace.get_events_by_type(TraceEventType.RUN_STARTED)
        assert len(events) == 1
        assert events[0].event_type == TraceEventType.RUN_STARTED


class TestReplayServiceComparison:
    def test_compare_identical_traces(self) -> None:
        trace = _sample_trace()
        service = ReplayService()
        comparison = service.compare_traces(trace, trace)

        assert comparison.winner == "tie"
        assert comparison.baseline_run_id == "run-123"
        assert comparison.comparison_run_id == "run-123"

    def test_compare_different_traces(self) -> None:
        trace_a = _sample_trace()
        trace_b = ExecutionTrace(
            run_id="run-456",
            provider_name="openai",
            model_id="gpt-4",
            item_traces=(
                ItemTrace(
                    item_index=0,
                    prompt_trace=PromptTrace(prompt="What is 2+2?"),
                    metric_traces=(
                        MetricTrace(
                            metric_name="correctness",
                            score=0.6,
                            normalized_score=0.6,
                        ),
                    ),
                ),
            ),
        )

        service = ReplayService()
        comparison = service.compare_traces(trace_a, trace_b)

        assert comparison.winner == "baseline"
        assert comparison.baseline_run_id == "run-123"
        assert comparison.comparison_run_id == "run-456"
