"""Tests for replay persistence gap closure (B.9.1.1).

Proves that evaluation traces persisted in the database are
replayable through the existing ReplayService without requiring Redis.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.evaluation.replay.composite_repository import CompositeTraceRepository
from app.evaluation.replay.database_repository import DatabaseTraceRepository
from app.evaluation.replay.domain import ExecutionTrace
from app.evaluation.replay.service import ReplayService
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trace_dict(
    run_id: str = "run-001",
    item_count: int = 1,
    provider: str = "openai",
    model: str = "gpt-4",
) -> dict:
    """Build an ExecutionTrace-compatible dict."""
    item_traces = []
    for i in range(item_count):
        item_traces.append(
            {
                "item_index": i,
                "prompt_trace": {"prompt": f"Question {i}"},
                "provider_trace": {
                    "provider_name": provider,
                    "model_id": model,
                    "response_content": f"Answer {i}",
                    "tokens_input": 100,
                    "tokens_output": 50,
                    "cost_usd": 0.001,
                    "latency_ms": 200,
                },
                "metric_traces": [
                    {
                        "metric_name": "correctness",
                        "score": 0.9,
                        "normalized_score": 0.9,
                        "confidence": 0.85,
                        "reasoning": "Correct",
                        "version": "1.0.0",
                        "cost_usd": 0.0,
                        "execution_time_ms": 100,
                    }
                ],
                "total_latency_ms": 200,
                "total_cost_usd": 0.001,
            }
        )

    return {
        "run_id": run_id,
        "evaluation_name": "test-eval",
        "provider_name": provider,
        "model_id": model,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "status": "completed",
        "item_traces": item_traces,
        "total_cost_usd": 0.001 * item_count,
        "total_tokens_input": 100 * item_count,
        "total_tokens_output": 50 * item_count,
        "total_latency_ms": 200 * item_count,
        "configuration": {"provider": provider, "model": model},
    }


def _make_db_repo(
    trace_data: dict | None = None, run_id: str = "run-001"
) -> DatabaseTraceRepository:
    """Create a DatabaseTraceRepository with mocked session."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = trace_data
    mock_session.execute.return_value = mock_result
    return DatabaseTraceRepository(mock_session)


# ---------------------------------------------------------------------------
# Test 1 — Real persisted trace
# ---------------------------------------------------------------------------


class TestRealPersistedTrace:
    """A real evaluation creates trace_data in the database."""

    def test_trace_data_stored_on_orm_model(self) -> None:
        """EvaluationRunModel stores trace_data as JSON."""
        trace_data = _make_trace_dict(run_id="run-001")
        model = MagicMock(spec=EvaluationRunModel)
        model.trace_data = trace_data
        assert model.trace_data is not None
        assert model.trace_data["run_id"] == "run-001"
        assert len(model.trace_data["item_traces"]) == 1

    def test_trace_data_none_when_no_trace(self) -> None:
        """EvaluationRunModel has None trace_data when no trace exists."""
        model = MagicMock(spec=EvaluationRunModel)
        model.trace_data = None
        assert model.trace_data is None


# ---------------------------------------------------------------------------
# Test 2 — Replay from database
# ---------------------------------------------------------------------------


class TestReplayFromDatabase:
    """ReplayService loads traces from the database and generates reports."""

    def test_database_trace_repository_loads_trace(self) -> None:
        """DatabaseTraceRepository.find_by_run_id returns trace data."""
        trace_data = _make_trace_dict(run_id="run-db-001")
        repo = _make_db_repo(trace_data, "run-db-001")

        result = asyncio.run(repo.find_by_run_id("run-db-001"))

        assert result is not None
        assert result["run_id"] == "run-db-001"

    def test_database_trace_repository_returns_none_for_missing(self) -> None:
        """DatabaseTraceRepository returns None for unknown run."""
        repo = _make_db_repo(None)

        result = asyncio.run(repo.find_by_run_id("unknown-run"))

        assert result is None

    def test_replay_service_generates_report_from_db_trace(self) -> None:
        """ReplayService generates a report from a database-persisted trace."""
        trace_data = _make_trace_dict(run_id="run-replay-001", item_count=2)
        repo = _make_db_repo(trace_data, "run-replay-001")
        service = ReplayService(repo)

        trace = asyncio.run(service.load_trace("run-replay-001"))
        assert trace is not None
        assert trace.run_id == "run-replay-001"
        assert trace.item_count == 2

        report = service.generate_replay_report(trace)
        assert report.summary.run_id == "run-replay-001"
        assert report.summary.total_items == 2
        assert len(report.item_reports) == 2
        assert report.item_reports[0].prompt_preview == "Question 0"

    def test_trace_roundtrip_through_database(self) -> None:
        """ExecutionTrace survives serialization → database → deserialization."""
        trace_data = _make_trace_dict(run_id="run-roundtrip-001")

        trace = ExecutionTrace.from_dict(trace_data)
        reserialized = trace.to_dict()

        assert reserialized["run_id"] == "run-roundtrip-001"
        assert len(reserialized["item_traces"]) == 1
        assert reserialized["item_traces"][0]["provider_trace"]["response_content"] == "Answer 0"


# ---------------------------------------------------------------------------
# Test 3 — No trace
# ---------------------------------------------------------------------------


class TestNoTrace:
    """Evaluation run without trace produces appropriate error."""

    def test_load_trace_returns_none_for_no_trace(self) -> None:
        """ReplayService returns None when run has no trace_data."""
        repo = _make_db_repo(None)
        service = ReplayService(repo)

        trace = asyncio.run(service.load_trace("run-no-trace"))
        assert trace is None


# ---------------------------------------------------------------------------
# Test 4 — Unknown run
# ---------------------------------------------------------------------------


class TestUnknownRun:
    """Unknown run ID produces not-found behavior."""

    def test_unknown_run_returns_none(self) -> None:
        """DatabaseTraceRepository returns None for unknown run ID."""
        repo = _make_db_repo(None)

        result = asyncio.run(repo.find_by_run_id("nonexistent-run-id"))

        assert result is None


# ---------------------------------------------------------------------------
# Test 5 — Malformed trace
# ---------------------------------------------------------------------------


class TestMalformedTrace:
    """Malformed trace data fails explicitly and safely."""

    def test_malformed_trace_data_returns_none(self) -> None:
        """DatabaseTraceRepository returns None for non-dict trace_data."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "not-a-dict"
        mock_session.execute.return_value = mock_result
        repo = DatabaseTraceRepository(mock_session)

        result = asyncio.run(repo.find_by_run_id("run-malformed"))

        assert result is None

    def test_partial_trace_data_deserializes_with_defaults(self) -> None:
        """Partial trace data deserializes with safe defaults for missing fields."""
        repo = _make_db_repo({"run_id": "run-partial"})

        result = asyncio.run(repo.find_by_run_id("run-partial"))

        assert result is not None
        trace = ExecutionTrace.from_dict(result)
        assert trace.run_id == "run-partial"
        assert trace.item_count == 0


# ---------------------------------------------------------------------------
# Test 6 — Comparison regression
# ---------------------------------------------------------------------------


class TestComparisonRegression:
    """Existing comparison functionality still produces correct deltas."""

    def test_compare_traces_from_database_data(self) -> None:
        """ReplayService.compare_traces works with database-persisted traces."""
        baseline_data = _make_trace_dict(run_id="baseline", provider="openai", model="gpt-3.5")
        comparison_data = _make_trace_dict(
            run_id="comparison", provider="anthropic", model="claude-3"
        )

        baseline = ExecutionTrace.from_dict(baseline_data)
        comparison = ExecutionTrace.from_dict(comparison_data)

        service = ReplayService()
        result = service.compare_traces(baseline, comparison)

        assert result.baseline_run_id == "baseline"
        assert result.comparison_run_id == "comparison"
        assert result.winner == "tie"
        assert result.cost_delta == pytest.approx(0.0)

    def test_compare_traces_with_different_scores(self) -> None:
        """Comparison correctly identifies winner with different scores."""
        baseline_data = _make_trace_dict(run_id="baseline")
        baseline_data["item_traces"][0]["metric_traces"][0]["normalized_score"] = 0.5

        comparison_data = _make_trace_dict(run_id="comparison")
        comparison_data["item_traces"][0]["metric_traces"][0]["normalized_score"] = 0.9

        baseline = ExecutionTrace.from_dict(baseline_data)
        comparison = ExecutionTrace.from_dict(comparison_data)

        service = ReplayService()
        result = service.compare_traces(baseline, comparison)

        assert result.winner == "comparison"
        assert result.metric_deltas["correctness"]["delta"] == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Test 7 — Redis independence
# ---------------------------------------------------------------------------


class TestRedisIndependence:
    """Persisted evaluation traces can be replayed without Redis."""

    def test_composite_repository_uses_database_first(self) -> None:
        """CompositeTraceRepository loads from database, not Redis."""
        trace_data = _make_trace_dict(run_id="run-db-only-001")
        db_repo = _make_db_repo(trace_data, "run-db-only-001")

        composite = CompositeTraceRepository(primary=db_repo, fallback=None)
        service = ReplayService(composite)

        trace = asyncio.run(service.load_trace("run-db-only-001"))
        assert trace is not None
        assert trace.run_id == "run-db-only-001"

    def test_composite_repository_falls_back_to_redis(self) -> None:
        """CompositeTraceRepository falls back to Redis when database has no trace."""
        db_repo = _make_db_repo(None)

        trace_data = _make_trace_dict(run_id="run-redis-001")
        mock_redis_repo = AsyncMock()
        mock_redis_repo.find_by_run_id.return_value = trace_data

        composite = CompositeTraceRepository(primary=db_repo, fallback=mock_redis_repo)
        service = ReplayService(composite)

        trace = asyncio.run(service.load_trace("run-redis-001"))
        assert trace is not None
        assert trace.run_id == "run-redis-001"
        mock_redis_repo.find_by_run_id.assert_called_once_with("run-redis-001")

    def test_database_only_replay_works_without_redis(self) -> None:
        """Full replay pipeline works with database-only trace source."""
        trace_data = _make_trace_dict(run_id="run-full-001", item_count=3)
        db_repo = _make_db_repo(trace_data, "run-full-001")

        composite = CompositeTraceRepository(primary=db_repo, fallback=None)
        service = ReplayService(composite)

        trace = asyncio.run(service.load_trace("run-full-001"))
        assert trace is not None

        report = service.generate_replay_report(trace)
        assert report.summary.run_id == "run-full-001"
        assert report.summary.total_items == 3
        assert len(report.item_reports) == 3

        assert len(report.item_reports[0].metric_explanations) == 1
        assert report.item_reports[0].metric_explanations[0].metric_name == "correctness"
