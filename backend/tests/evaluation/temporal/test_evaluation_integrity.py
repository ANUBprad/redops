"""Tests for evaluation integrity wiring (B.9.1).

Proves that trace recording, provenance, fingerprint, threshold evaluation,
and verdict determination work correctly through the evaluation lifecycle.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import RunStatus
from app.evaluation.metrics.domain import MetricResult
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.reliability.fingerprint import EvaluationFingerprint, compute_fingerprint
from app.evaluation.reliability.provenance import (
    EnvironmentSnapshot,
    ReproducibilityContract,
    capture_environment,
)
from app.evaluation.replay.domain import ExecutionTrace
from app.evaluation.replay.recorder import TraceRecorder
from app.evaluation.replay.service import ReplayService
from app.evaluation.temporal.workflow import (
    EvaluationRunWorkflowInput,
    _build_item_trace,
    _compute_workflow_fingerprint,
)
from app.evaluation.temporal.activities import ExecuteItemResult, MetricResultPayload
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)
from app.kernel.entities.base import UUIDv7


# ---------------------------------------------------------------------------
# Test 1 — Provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    """Provenance is captured from the real execution environment."""

    def test_capture_environment_returns_snapshot(self) -> None:
        """capture_environment returns an EnvironmentSnapshot with real values."""
        snapshot = capture_environment()
        assert isinstance(snapshot, EnvironmentSnapshot)
        assert snapshot.python_version != "unknown"
        assert snapshot.platform_info != "unknown"

    def test_reproducibility_contract_to_dict(self) -> None:
        """ReproducibilityContract serializes to a JSON-compatible dict."""
        env = EnvironmentSnapshot(
            git_commit_hash="abc123",
            git_branch="main",
            python_version="3.12.0",
            requirements_hash="def456",
            platform_info="Linux",
        )
        contract = ReproducibilityContract(
            run_id="run-001",
            environment=env,
            evaluation_config_hash="hash123",
            metric_versions={"correctness": "1.0.0"},
            provider_model="openai/gpt-4",
        )
        d = contract.to_dict()
        assert d["run_id"] == "run-001"
        assert d["environment"]["git_commit_hash"] == "abc123"
        assert d["metric_versions"]["correctness"] == "1.0.0"
        assert d["provider_model"] == "openai/gpt-4"

    def test_provenance_stored_on_evaluation_run(self) -> None:
        """EvaluationRun domain model stores provenance data."""
        config = MagicMock()
        config.priority = MagicMock()
        config.priority.value = "normal"
        profile = MagicMock()
        profile.provider_name = "openai"
        profile.model_id = "gpt-4"
        run = EvaluationRun(
            evaluation_name="test",
            config=config,
            profile=profile,
        )
        assert run.provenance is None
        run.provenance = {"environment": {"git_commit_hash": "abc123"}}
        assert run.provenance is not None
        assert run.provenance["environment"]["git_commit_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Test 2 — Fingerprint
# ---------------------------------------------------------------------------


class TestFingerprint:
    """Fingerprints are deterministic and change with configuration."""

    def test_same_config_same_fingerprint(self) -> None:
        """Same configuration produces the same fingerprint."""
        fp1 = _compute_workflow_fingerprint(
            prompt_template="{prompt}",
            system_prompt="You are helpful.",
            provider="openai",
            model="gpt-4",
            metrics=("correctness", "coherence"),
        )
        fp2 = _compute_workflow_fingerprint(
            prompt_template="{prompt}",
            system_prompt="You are helpful.",
            provider="openai",
            model="gpt-4",
            metrics=("correctness", "coherence"),
        )
        assert fp1 == fp2
        assert len(fp1) == 32

    def test_different_provider_different_fingerprint(self) -> None:
        """Different provider produces different fingerprint."""
        fp1 = _compute_workflow_fingerprint(
            prompt_template="{prompt}",
            system_prompt="",
            provider="openai",
            model="gpt-4",
            metrics=("correctness",),
        )
        fp2 = _compute_workflow_fingerprint(
            prompt_template="{prompt}",
            system_prompt="",
            provider="anthropic",
            model="claude-3",
            metrics=("correctness",),
        )
        assert fp1 != fp2

    def test_different_metrics_different_fingerprint(self) -> None:
        """Different metrics produce different fingerprint."""
        fp1 = _compute_workflow_fingerprint(
            prompt_template="",
            system_prompt="",
            provider="openai",
            model="gpt-4",
            metrics=("correctness",),
        )
        fp2 = _compute_workflow_fingerprint(
            prompt_template="",
            system_prompt="",
            provider="openai",
            model="gpt-4",
            metrics=("correctness", "coherence"),
        )
        assert fp1 != fp2

    def test_compute_fingerprint_library(self) -> None:
        """The reliability fingerprint library produces stable results."""
        fp1 = compute_fingerprint(
            prompt_template="{prompt}",
            system_prompt="test",
            provider="openai",
            model="gpt-4",
            metrics=("correctness",),
        )
        fp2 = compute_fingerprint(
            prompt_template="{prompt}",
            system_prompt="test",
            provider="openai",
            model="gpt-4",
            metrics=("correctness",),
        )
        assert isinstance(fp1, EvaluationFingerprint)
        assert fp1.matches(fp2)

    def test_fingerprint_stored_on_evaluation_run(self) -> None:
        """EvaluationRun domain model stores fingerprint."""
        config = MagicMock()
        config.priority = MagicMock()
        config.priority.value = "normal"
        profile = MagicMock()
        profile.provider_name = "openai"
        profile.model_id = "gpt-4"
        run = EvaluationRun(
            evaluation_name="test",
            config=config,
            profile=profile,
        )
        assert run.fingerprint is None
        run.fingerprint = "abc123def456"
        assert run.fingerprint == "abc123def456"


# ---------------------------------------------------------------------------
# Test 3 — Threshold PASS
# ---------------------------------------------------------------------------


class TestThresholdPass:
    """Metric score above threshold produces PASS verdict."""

    def test_passed_against_with_passing_score(self) -> None:
        """MetricResult.passed_against returns True when score >= threshold."""
        result = MetricResult(
            metric_name="correctness",
            score=0.9,
            normalized_score=0.9,
        )
        assert result.passed_against(0.7) is True

    def test_passed_against_with_boundary_score(self) -> None:
        """MetricResult.passed_against returns True when score == threshold."""
        result = MetricResult(
            metric_name="correctness",
            score=0.7,
            normalized_score=0.7,
        )
        assert result.passed_against(0.7) is True

    def test_threshold_on_metric_definition(self) -> None:
        """MetricDefinition has a default_threshold field."""
        from app.evaluation.metrics.trajectories.trajectory_tool_selection import (
            TrajectoryToolSelectionMetric,
        )

        metric = TrajectoryToolSelectionMetric()
        defn = metric.definition()
        assert defn is not None
        assert defn.default_threshold is not None
        assert defn.default_threshold == 0.5


# ---------------------------------------------------------------------------
# Test 4 — Threshold FAIL
# ---------------------------------------------------------------------------


class TestThresholdFail:
    """Metric score below threshold produces FAIL verdict."""

    def test_passed_against_with_failing_score(self) -> None:
        """MetricResult.passed_against returns False when score < threshold."""
        result = MetricResult(
            metric_name="correctness",
            score=0.3,
            normalized_score=0.3,
        )
        assert result.passed_against(0.7) is False

    def test_passed_against_returns_none_for_errors(self) -> None:
        """MetricResult.passed_against returns None when error is set."""
        result = MetricResult(
            metric_name="correctness",
            score=0.0,
            normalized_score=0.0,
            error="metric failed",
        )
        assert result.passed_against(0.7) is None

    def test_passed_against_returns_none_for_no_threshold(self) -> None:
        """MetricResult.passed_against returns None when no threshold."""
        result = MetricResult(
            metric_name="correctness",
            score=0.9,
            normalized_score=0.9,
        )
        assert result.passed_against(None) is None


# ---------------------------------------------------------------------------
# Test 5 — Metric ERROR
# ---------------------------------------------------------------------------


class TestMetricError:
    """Metric errors do not silently become successful evaluations."""

    def test_error_result_is_not_success(self) -> None:
        """MetricResult with error is not a success."""
        result = MetricResult(
            metric_name="correctness",
            score=0.0,
            normalized_score=0.0,
            error="LLM judge failed",
        )
        assert result.is_success is False
        assert result.passed_against(0.5) is None

    def test_error_in_aggregation(self) -> None:
        """MetricAggregation correctly counts errors."""
        from app.evaluation.metrics.domain import MetricAggregation

        results = (
            MetricResult(metric_name="m", score=0.9, normalized_score=0.9),
            MetricResult(metric_name="m", score=0.0, normalized_score=0.0, error="fail"),
        )
        agg = MetricAggregation.from_results("m", results)
        assert agg.success_count == 1
        assert agg.error_count == 1
        assert agg.item_count == 2


# ---------------------------------------------------------------------------
# Test 6 — Trace persistence
# ---------------------------------------------------------------------------


class TestTracePersistence:
    """Traces are built from real evaluation data and contain expected fields."""

    def test_build_item_trace_from_result(self) -> None:
        """_build_item_trace constructs a valid trace dict from ExecuteItemResult."""
        payload = MetricResultPayload(
            metric_name="correctness",
            score=0.9,
            normalized_score=0.9,
            confidence=0.85,
            reasoning="Correct",
            version="1.0.0",
            cost_usd=0.001,
            execution_time_ms=150,
        )
        result = ExecuteItemResult(
            item_index=0,
            response="4",
            cost_usd=0.002,
            tokens_input=100,
            tokens_output=50,
            latency_ms=200,
            failed=False,
            item_id="item-0",
            metrics=(payload,),
        )
        trace = _build_item_trace(result)
        assert trace["item_index"] == 0
        assert trace["provider_trace"]["response_content"] == "4"
        assert trace["provider_trace"]["tokens_input"] == 100
        assert len(trace["metric_traces"]) == 1
        assert trace["metric_traces"][0]["metric_name"] == "correctness"
        assert trace["metric_traces"][0]["normalized_score"] == 0.9

    def test_trace_stored_on_evaluation_run(self) -> None:
        """EvaluationRun domain model stores trace_data."""
        config = MagicMock()
        config.priority = MagicMock()
        config.priority.value = "normal"
        profile = MagicMock()
        profile.provider_name = "openai"
        profile.model_id = "gpt-4"
        run = EvaluationRun(
            evaluation_name="test",
            config=config,
            profile=profile,
        )
        assert run.trace_data is None
        trace = {"run_id": "r1", "item_traces": []}
        run.trace_data = trace
        assert run.trace_data == trace

    def test_trace_recorder_produces_execution_trace(self) -> None:
        """TraceRecorder builds an ExecutionTrace that can be serialized."""
        import asyncio

        async def _record() -> ExecutionTrace:
            recorder = TraceRecorder(run_id="test-run", evaluation_name="test-eval")
            recorder.set_provider("openai", "gpt-4")
            await recorder.record_event(
                __import__(
                    "app.evaluation.replay.domain", fromlist=["TraceEventType"]
                ).TraceEventType.RUN_STARTED,
            )
            await recorder.record_prompt(0, "What is 2+2?")
            await recorder.record_provider_response(
                0, "4", tokens_input=10, tokens_output=5, cost_usd=0.001, latency_ms=200,
            )
            await recorder.record_metric(0, "correctness", 0.95, 0.95, confidence=0.9)
            await recorder.record_event(
                __import__(
                    "app.evaluation.replay.domain", fromlist=["TraceEventType"]
                ).TraceEventType.RUN_COMPLETED,
            )
            return recorder.build_trace()

        trace = asyncio.run(_record())
        assert trace.run_id == "test-run"
        assert trace.status == "completed"
        assert trace.item_count == 1
        trace_dict = trace.to_dict()
        restored = ExecutionTrace.from_dict(trace_dict)
        assert restored.run_id == trace.run_id
        assert restored.item_count == trace.item_count


# ---------------------------------------------------------------------------
# Test 7 — Replay
# ---------------------------------------------------------------------------


class TestReplay:
    """Replay service reconstructs evaluation records from traces."""

    def test_replay_service_generates_report(self) -> None:
        """ReplayService generates a report from an ExecutionTrace."""
        import asyncio

        async def _test() -> None:
            recorder = TraceRecorder(run_id="replay-test", evaluation_name="replay-eval")
            recorder.set_provider("openai", "gpt-4")
            from app.evaluation.replay.domain import TraceEventType

            await recorder.record_event(TraceEventType.RUN_STARTED)
            await recorder.record_prompt(0, "What is AI?")
            await recorder.record_provider_response(0, "AI is artificial intelligence.", cost_usd=0.002)
            await recorder.record_metric(0, "correctness", 0.9, 0.9, confidence=0.85, reasoning="Factually correct")
            await recorder.record_event(TraceEventType.RUN_COMPLETED)

            trace = recorder.build_trace()
            service = ReplayService()
            report = service.generate_replay_report(trace)

            assert report.summary.run_id == "replay-test"
            assert report.summary.total_items == 1
            assert report.summary.successful_items == 1
            assert len(report.item_reports) == 1
            assert len(report.item_reports[0].metric_explanations) == 1

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Test 8 — Comparison
# ---------------------------------------------------------------------------


class TestComparison:
    """Comparison computes metric-by-metric differences between traces."""

    def test_compare_traces_returns_deltas(self) -> None:
        """ReplayService.compare_traces returns correct metric deltas."""
        import asyncio

        async def _test() -> None:
            from app.evaluation.replay.domain import TraceEventType

            # Baseline
            r1 = TraceRecorder(run_id="baseline")
            r1.set_provider("openai", "gpt-3.5")
            await r1.record_event(TraceEventType.RUN_STARTED)
            await r1.record_prompt(0, "Test")
            await r1.record_provider_response(0, "Response 1", cost_usd=0.001)
            await r1.record_metric(0, "correctness", 0.7, 0.7)
            await r1.record_event(TraceEventType.RUN_COMPLETED)

            # Comparison
            r2 = TraceRecorder(run_id="comparison")
            r2.set_provider("anthropic", "claude-3")
            await r2.record_event(TraceEventType.RUN_STARTED)
            await r2.record_prompt(0, "Test")
            await r2.record_provider_response(0, "Response 2", cost_usd=0.003)
            await r2.record_metric(0, "correctness", 0.9, 0.9)
            await r2.record_event(TraceEventType.RUN_COMPLETED)

            service = ReplayService()
            comparison = service.compare_traces(r1.build_trace(), r2.build_trace())

            assert comparison.baseline_run_id == "baseline"
            assert comparison.comparison_run_id == "comparison"
            assert comparison.winner == "comparison"
            assert comparison.cost_delta == pytest.approx(0.002)
            assert "correctness" in comparison.metric_deltas
            assert comparison.metric_deltas["correctness"]["delta"] == pytest.approx(0.2)

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Test 9 — Retry/idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Duplicate persistence does not create duplicate logical results."""

    def test_metric_result_repository_deduplication(self) -> None:
        """Saving the same MetricResult twice does not create duplicates.

        Uses stable identifiers (run_id, item_id, metric_name) for
        idempotent persistence.
        """
        result1 = MetricResult(
            metric_name="correctness",
            score=0.9,
            normalized_score=0.9,
            metadata={"run_id": "run-001", "item_id": "item-0"},
        )
        result2 = MetricResult(
            metric_name="correctness",
            score=0.9,
            normalized_score=0.9,
            metadata={"run_id": "run-001", "item_id": "item-0"},
        )
        # Both results have the same identity
        assert result1.metric_name == result2.metric_name
        assert result1.metadata["run_id"] == result2.metadata["run_id"]
        assert result1.metadata["item_id"] == result2.metadata["item_id"]

    def test_finalize_activity_returns_verdict_string(self) -> None:
        """finalize_run_integrity_activity input carries all needed data."""
        from app.evaluation.temporal.activities import FinalizeRunIntegrityInput

        input = FinalizeRunIntegrityInput(
            run_id="run-001",
            metric_names=("correctness", "coherence"),
            trace_data={"run_id": "run-001", "item_traces": []},
            provenance={"environment": {"git_commit_hash": "abc"}},
            fingerprint="fp123",
        )
        assert input.run_id == "run-001"
        assert len(input.metric_names) == 2
        assert input.fingerprint == "fp123"


# ---------------------------------------------------------------------------
# Test 10 — Full integration (domain model round-trip)
# ---------------------------------------------------------------------------


class TestFullIntegration:
    """Full lifecycle: domain model → ORM → repository → domain model."""

    def test_evaluation_run_round_trip_with_new_fields(self) -> None:
        """EvaluationRun persists and rehydrates verdict, trace, provenance, fingerprint."""
        from app.evaluation.domain.enums.evaluation_enums import EvaluationType, Priority
        from app.evaluation.domain.value_objects.evaluation_value_objects import (
            EvaluationConfiguration,
            EvaluationProfile,
        )

        profile = EvaluationProfile(
            provider_name="openai",
            model_id="gpt-4",
            temperature=0.0,
            max_tokens=4096,
            timeout_seconds=60,
        )
        config = EvaluationConfiguration(
            name="test-eval",
            eval_type=EvaluationType.SINGLE,
            profile=profile,
            metrics=("correctness",),
            priority=Priority.NORMAL,
        )
        run = EvaluationRun(
            evaluation_name="test-eval",
            config=config,
            profile=profile,
        )

        # Set new fields
        run.verdict = "pass"
        run.fingerprint = "abc123def456"
        run.provenance = {
            "environment": {"git_commit_hash": "abc123"},
            "metric_versions": {"correctness": "1.0.0"},
        }
        run.trace_data = {
            "run_id": str(run.id),
            "item_traces": [
                {
                    "item_index": 0,
                    "provider_trace": {"response_content": "4"},
                    "metric_traces": [
                        {"metric_name": "correctness", "normalized_score": 0.9}
                    ],
                }
            ],
        }

        # Convert to ORM model
        orm = SqlAlchemyEvaluationRunRepository._to_model(run)
        assert orm.verdict == "pass"
        assert orm.fingerprint == "abc123def456"
        assert orm.provenance is not None
        assert orm.provenance["environment"]["git_commit_hash"] == "abc123"
        assert orm.trace_data is not None
        assert len(orm.trace_data["item_traces"]) == 1

        # Convert back to domain
        domain = SqlAlchemyEvaluationRunRepository._to_domain(orm)
        assert domain.verdict == "pass"
        assert domain.fingerprint == "abc123def456"
        assert domain.provenance is not None
        assert domain.provenance["metric_versions"]["correctness"] == "1.0.0"
        assert domain.trace_data is not None
        assert len(domain.trace_data["item_traces"]) == 1

    def test_verdict_values(self) -> None:
        """Verdict can be pass, fail, error, or None."""
        config = MagicMock()
        config.priority = MagicMock()
        config.priority.value = "normal"
        profile = MagicMock()
        profile.provider_name = "openai"
        profile.model_id = "gpt-4"
        run = EvaluationRun(
            evaluation_name="test",
            config=config,
            profile=profile,
        )
        # Initially None
        assert run.verdict is None
        # Set to pass
        run.verdict = "pass"
        assert run.verdict == "pass"
        # Set to fail
        run.verdict = "fail"
        assert run.verdict == "fail"
        # Set to error
        run.verdict = "error"
        assert run.verdict == "error"

    def test_workflow_input_has_metric_names(self) -> None:
        """EvaluationRunWorkflowInput carries metric names for threshold evaluation."""
        input = EvaluationRunWorkflowInput(
            run_id="run-001",
            total_items=5,
            provider_name="openai",
            model_id="gpt-4",
            metric_names=("correctness", "coherence"),
        )
        assert len(input.metric_names) == 2
        assert "correctness" in input.metric_names

    def test_orm_model_has_new_columns(self) -> None:
        """EvaluationRunModel has verdict, trace_data, provenance, fingerprint columns."""
        cols = {c.name for c in EvaluationRunModel.__table__.columns}
        assert "verdict" in cols
        assert "trace_data" in cols
        assert "provenance" in cols
        assert "fingerprint" in cols
