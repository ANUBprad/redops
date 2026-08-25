"""Integration tests for agent trajectory evaluation.

Proves the complete path:
  AGENT TASK → AGENT EXECUTION → MODEL ACTION → TOOL CALL →
  TOOL RESULT → NEXT ACTION → FINAL RESPONSE → COMPLETE TRAJECTORY →
  TRAJECTORY METRICS → PERSISTED EVALUATION RESULT

All tests are deterministic — no external services, no real LLM calls.
All async tests use synchronous wrappers (pytest-asyncio not installed).
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.domain.tool_execution import (
    SafeToolExecutor,
    ToolDefinition,
    ToolRegistry,
)
from app.agents.domain.trajectory import (
    AgentTrajectory,
    LLMCallRecord,
    ToolCallRecord,
    TrajectoryStatus,
    TrajectoryStep,
    TrajectoryStepType,
    compute_trajectory_metrics,
)
from app.agents.runtime.trajectory_recorder import TrajectoryRecorder
from app.evaluation.metrics.domain import MetricInput
from app.evaluation.metrics.trajectories import (
    TrajectoryCompletenessMetric,
    TrajectoryEfficiencyMetric,
    TrajectoryErrorRecoveryMetric,
    TrajectoryToolSelectionMetric,
)
from app.evaluation.metrics.trajectories.evaluator import (
    TrajectoryEvaluationResult,
    TrajectoryEvaluator,
)


def _run_async(coro):
    """Run an async coroutine synchronously (pytest-asyncio not installed)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Test helpers — deterministic tool implementations
# ---------------------------------------------------------------------------


def _calculator(expression: str) -> str:
    """Safe calculator tool for testing."""
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expression):
        return "Error: invalid characters in expression"
    try:
        result = eval(expression)  # noqa: S307
        return str(result)
    except Exception as exc:
        return f"Error: {exc}"


def _lookup(query: str) -> str:
    """Deterministic lookup tool for testing."""
    data = {
        "python": "Python is a programming language",
        "rust": "Rust is a systems programming language",
        "redops": "RedOps is an AI security evaluation platform",
    }
    result = data.get(query.lower(), f"No result for '{query}'")
    return result


def _always_fails(reason: str = "simulated failure") -> str:
    """Tool that always fails for testing error recovery."""
    raise RuntimeError(reason)


def _build_test_tool_registry() -> ToolRegistry:
    """Build a tool registry with test tools."""
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="calculator",
            description="Evaluate a mathematical expression",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate",
                    }
                },
                "required": ["expression"],
            },
        ),
        _calculator,
    )
    registry.register(
        ToolDefinition(
            name="lookup",
            description="Look up information about a topic",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    }
                },
                "required": ["query"],
            },
        ),
        _lookup,
    )
    registry.register(
        ToolDefinition(
            name="failing_tool",
            description="A tool that always fails",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                },
            },
        ),
        _always_fails,
    )
    return registry


def _build_trajectory_dict(
    *,
    trajectory_id: str = "test-traj-001",
    run_id: str = "test-run-001",
    status: str = "completed",
    steps: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a serialized trajectory dict for metric evaluation."""
    return {
        "trajectory_id": trajectory_id,
        "run_id": run_id,
        "agent_name": "test_agent",
        "task_description": "test task",
        "status": status,
        "steps": steps or [],
        "metrics": metrics
        or {
            "total_steps": 0,
            "llm_calls": 0,
            "tool_calls": 0,
            "tool_results": 0,
            "errors": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "total_cost_usd": 0.0,
            "total_duration_ms": 0,
            "unique_tools_used": [],
            "tool_error_rate": 0.0,
            "average_llm_latency_ms": 0.0,
            "average_tool_latency_ms": 0.0,
        },
        "conversation_history": [],
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:01Z",
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Unit tests — Trajectory domain model
# ---------------------------------------------------------------------------


class TestTrajectoryDomain:
    """Tests for trajectory domain value objects."""

    def test_trajectory_step_creation(self) -> None:
        step = TrajectoryStep(
            step_index=0,
            step_type=TrajectoryStepType.LLM_CALL,
            content="Hello",
        )
        assert step.step_index == 0
        assert step.step_type == TrajectoryStepType.LLM_CALL
        assert step.content == "Hello"
        assert not step.is_error
        assert step.tokens_used == 0
        assert step.cost_usd == 0.0

    def test_trajectory_step_error(self) -> None:
        step = TrajectoryStep(
            step_index=0,
            step_type=TrajectoryStepType.ERROR,
            error="something went wrong",
        )
        assert step.is_error

    def test_trajectory_step_with_llm_call(self) -> None:
        llm = LLMCallRecord(
            provider="openai",
            model="gpt-4",
            tokens_input=100,
            tokens_output=50,
            cost_usd=0.01,
        )
        step = TrajectoryStep(
            step_index=0,
            step_type=TrajectoryStepType.LLM_CALL,
            llm_call=llm,
        )
        assert step.tokens_used == 150
        assert step.cost_usd == 0.01

    def test_tool_call_record(self) -> None:
        tc = ToolCallRecord(
            tool_call_id="call-1",
            tool_name="calculator",
            arguments={"expression": "2+2"},
            result="4",
        )
        assert tc.tool_name == "calculator"
        assert tc.result == "4"
        assert not tc.is_error

    def test_trajectory_final_response(self) -> None:
        steps = (
            TrajectoryStep(
                step_index=0,
                step_type=TrajectoryStepType.LLM_CALL,
                content="Let me calculate",
            ),
            TrajectoryStep(
                step_index=1,
                step_type=TrajectoryStepType.FINAL_ANSWER,
                content="The answer is 4",
            ),
        )
        traj = AgentTrajectory(
            trajectory_id="t1",
            run_id="r1",
            steps=steps,
        )
        assert traj.final_response == "The answer is 4"
        assert traj.step_count == 2

    def test_trajectory_all_tool_calls(self) -> None:
        tc1 = ToolCallRecord(tool_call_id="c1", tool_name="calc", arguments={})
        tc2 = ToolCallRecord(tool_call_id="c2", tool_name="lookup", arguments={})
        steps = (
            TrajectoryStep(
                step_index=0,
                step_type=TrajectoryStepType.LLM_CALL,
                llm_call=LLMCallRecord(
                    provider="openai",
                    model="gpt-4",
                    tool_calls_requested=(tc1,),
                ),
            ),
            TrajectoryStep(
                step_index=1,
                step_type=TrajectoryStepType.TOOL_CALL,
                tool_call=tc2,
            ),
        )
        traj = AgentTrajectory(
            trajectory_id="t1",
            run_id="r1",
            steps=steps,
        )
        all_calls = traj.all_tool_calls
        assert len(all_calls) == 2

    def test_trajectory_serialization_roundtrip(self) -> None:
        steps = (
            TrajectoryStep(
                step_index=0,
                step_type=TrajectoryStepType.LLM_CALL,
                llm_call=LLMCallRecord(
                    provider="openai",
                    model="gpt-4",
                    response_content="I'll help",
                    tokens_input=50,
                    tokens_output=20,
                    cost_usd=0.005,
                    latency_ms=100,
                    tool_calls_requested=(
                        ToolCallRecord(
                            tool_call_id="c1",
                            tool_name="calculator",
                            arguments={"expression": "2+2"},
                        ),
                    ),
                ),
                content="I'll help",
            ),
            TrajectoryStep(
                step_index=1,
                step_type=TrajectoryStepType.TOOL_CALL,
                tool_call=ToolCallRecord(
                    tool_call_id="c1",
                    tool_name="calculator",
                    arguments={"expression": "2+2"},
                    result="4",
                    latency_ms=5,
                ),
                content="4",
            ),
            TrajectoryStep(
                step_index=2,
                step_type=TrajectoryStepType.FINAL_ANSWER,
                content="The answer is 4",
            ),
        )
        traj = AgentTrajectory(
            trajectory_id="t-123",
            run_id="r-456",
            agent_name="calc_agent",
            status=TrajectoryStatus.COMPLETED,
            steps=steps,
            metrics=compute_trajectory_metrics(steps),
        )

        data = traj.to_dict()
        restored = AgentTrajectory.from_dict(data)

        assert restored.trajectory_id == "t-123"
        assert restored.run_id == "r-456"
        assert restored.step_count == 3
        assert restored.final_response == "The answer is 4"
        assert restored.metrics.total_steps == 3
        assert restored.metrics.tool_calls == 1
        assert restored.metrics.llm_calls == 1


# ---------------------------------------------------------------------------
# Unit tests — compute_trajectory_metrics
# ---------------------------------------------------------------------------


class TestComputeTrajectoryMetrics:
    """Tests for the trajectory metrics computation."""

    def test_empty_steps(self) -> None:
        metrics = compute_trajectory_metrics(())
        assert metrics.total_steps == 0
        assert metrics.tool_calls == 0

    def test_llm_only_trajectory(self) -> None:
        steps = (
            TrajectoryStep(
                step_index=0,
                step_type=TrajectoryStepType.LLM_CALL,
                llm_call=LLMCallRecord(
                    provider="openai",
                    model="gpt-4",
                    tokens_input=100,
                    tokens_output=50,
                    cost_usd=0.01,
                    latency_ms=200,
                ),
            ),
            TrajectoryStep(
                step_index=1,
                step_type=TrajectoryStepType.FINAL_ANSWER,
                content="Done",
            ),
        )
        metrics = compute_trajectory_metrics(steps)
        assert metrics.total_steps == 2
        assert metrics.llm_calls == 1
        assert metrics.tool_calls == 0
        assert metrics.total_tokens_input == 100
        assert metrics.total_tokens_output == 50
        assert metrics.total_cost_usd == 0.01

    def test_tool_call_trajectory(self) -> None:
        steps = (
            TrajectoryStep(
                step_index=0,
                step_type=TrajectoryStepType.LLM_CALL,
                llm_call=LLMCallRecord(
                    provider="openai",
                    model="gpt-4",
                    tokens_input=80,
                    tokens_output=30,
                    cost_usd=0.005,
                    latency_ms=150,
                    tool_calls_requested=(
                        ToolCallRecord(
                            tool_call_id="c1",
                            tool_name="calculator",
                            latency_ms=5,
                        ),
                    ),
                ),
            ),
            TrajectoryStep(
                step_index=1,
                step_type=TrajectoryStepType.TOOL_CALL,
                tool_call=ToolCallRecord(
                    tool_call_id="c1",
                    tool_name="calculator",
                    result="4",
                    latency_ms=5,
                ),
            ),
            TrajectoryStep(
                step_index=2,
                step_type=TrajectoryStepType.LLM_CALL,
                llm_call=LLMCallRecord(
                    provider="openai",
                    model="gpt-4",
                    tokens_input=110,
                    tokens_output=20,
                    cost_usd=0.006,
                    latency_ms=120,
                ),
            ),
            TrajectoryStep(
                step_index=3,
                step_type=TrajectoryStepType.FINAL_ANSWER,
                content="4",
            ),
        )
        metrics = compute_trajectory_metrics(steps)
        assert metrics.total_steps == 4
        assert metrics.llm_calls == 2
        assert metrics.tool_calls == 1
        assert metrics.unique_tools_used == ("calculator",)
        assert metrics.total_tokens_input == 190
        assert metrics.total_tokens_output == 50

    def test_error_trajectory(self) -> None:
        steps = (
            TrajectoryStep(
                step_index=0,
                step_type=TrajectoryStepType.TOOL_CALL,
                tool_call=ToolCallRecord(
                    tool_call_id="c1",
                    tool_name="failing_tool",
                    is_error=True,
                ),
            ),
            TrajectoryStep(
                step_index=1,
                step_type=TrajectoryStepType.ERROR,
                error="tool failed",
            ),
        )
        metrics = compute_trajectory_metrics(steps)
        assert metrics.errors == 1
        assert metrics.tool_error_rate == 1.0


# ---------------------------------------------------------------------------
# Unit tests — Tool execution boundary
# ---------------------------------------------------------------------------


class TestToolExecution:
    """Tests for ToolRegistry and SafeToolExecutor."""

    def test_register_and_execute_tool(self) -> None:
        registry = _build_test_tool_registry()
        executor = SafeToolExecutor(registry)

        result = executor.execute("calculator", {"expression": "2+3"})
        assert result.is_success
        assert result.result == "5"

    def test_lookup_tool(self) -> None:
        registry = _build_test_tool_registry()
        executor = SafeToolExecutor(registry)

        result = executor.execute("lookup", {"query": "python"})
        assert result.is_success
        assert "programming language" in result.result

    def test_unknown_tool(self) -> None:
        registry = _build_test_tool_registry()
        executor = SafeToolExecutor(registry)

        result = executor.execute("nonexistent", {})
        assert result.is_error
        assert "Unknown tool" in (result.error or "")

    def test_missing_required_argument(self) -> None:
        registry = _build_test_tool_registry()
        executor = SafeToolExecutor(registry)

        result = executor.execute("calculator", {})
        assert result.is_error
        assert "Missing required" in (result.error or "")

    def test_tool_that_raises(self) -> None:
        registry = _build_test_tool_registry()
        executor = SafeToolExecutor(registry)

        result = executor.execute("failing_tool", {"reason": "test"})
        assert result.is_error
        assert result.error is not None
        assert "Tool execution failed" in result.error

    def test_registry_schemas(self) -> None:
        registry = _build_test_tool_registry()
        schemas = registry.get_openai_schemas()
        assert len(schemas) == 3
        names = {s["function"]["name"] for s in schemas}
        assert "calculator" in names
        assert "lookup" in names

    def test_registry_validation(self) -> None:
        registry = _build_test_tool_registry()
        error = registry.validate_tool_args("calculator", {"expression": "1+1"})
        assert error is None

        error = registry.validate_tool_args("calculator", {})
        assert error is not None


# ---------------------------------------------------------------------------
# Unit tests — Trajectory recorder
# ---------------------------------------------------------------------------


class TestTrajectoryRecorder:
    """Tests for the trajectory recorder."""

    def test_record_llm_call(self) -> None:
        recorder = TrajectoryRecorder(run_id="r1", agent_name="test")
        step = recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=1,
            response_content="I'll help",
            tokens_input=50,
            tokens_output=20,
            latency_ms=100,
        )
        assert step.step_type == TrajectoryStepType.LLM_CALL
        assert step.content == "I'll help"
        assert recorder.step_count == 1

    def test_record_tool_call(self) -> None:
        recorder = TrajectoryRecorder(run_id="r1")
        step = recorder.record_tool_call(
            tool_call_id="c1",
            tool_name="calculator",
            arguments={"expression": "2+2"},
            result="4",
            latency_ms=5,
        )
        assert step.step_type == TrajectoryStepType.TOOL_CALL
        assert step.tool_call is not None
        assert step.tool_call.result == "4"

    def test_record_final_answer(self) -> None:
        recorder = TrajectoryRecorder(run_id="r1")
        step = recorder.record_final_answer("The answer is 4")
        assert step.step_type == TrajectoryStepType.FINAL_ANSWER
        assert step.content == "The answer is 4"

    def test_build_trajectory(self) -> None:
        recorder = TrajectoryRecorder(
            run_id="r1",
            agent_name="test_agent",
            task_description="calculate 2+2",
        )
        recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=1,
            response_content="Let me calculate",
            tokens_input=50,
            tokens_output=20,
            tool_calls_requested=(
                ToolCallRecord(
                    tool_call_id="c1",
                    tool_name="calculator",
                    arguments={"expression": "2+2"},
                ),
            ),
        )
        recorder.record_tool_call(
            tool_call_id="c1",
            tool_name="calculator",
            arguments={"expression": "2+2"},
            result="4",
        )
        recorder.record_final_answer("The answer is 4")

        traj = recorder.build()
        assert traj.run_id == "r1"
        assert traj.agent_name == "test_agent"
        assert traj.step_count == 3
        assert traj.final_response == "The answer is 4"
        assert traj.metrics.tool_calls == 1

    def test_record_conversation_history(self) -> None:
        recorder = TrajectoryRecorder(run_id="r1")
        recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=1,
            response_content="Let me help",
            tool_calls_requested=(
                ToolCallRecord(
                    tool_call_id="c1",
                    tool_name="calc",
                    arguments={"expr": "1+1"},
                ),
            ),
        )
        recorder.record_tool_call(
            tool_call_id="c1",
            tool_name="calc",
            arguments={"expr": "1+1"},
            result="2",
        )
        recorder.record_final_answer("2")

        traj = recorder.build()
        history = traj.conversation_history
        assert len(history) == 3
        assert history[0]["role"] == "assistant"
        assert history[1]["role"] == "tool"
        assert history[2]["role"] == "assistant"


# ---------------------------------------------------------------------------
# Unit tests — Trajectory metrics (synchronous wrappers)
# ---------------------------------------------------------------------------


class TestTrajectoryMetrics:
    """Tests for trajectory evaluation metrics."""

    def _make_completed_trajectory(self) -> dict[str, Any]:
        return _build_trajectory_dict(
            status="completed",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "llm_call",
                    "content": "Let me calculate",
                    "llm_call": {
                        "provider": "openai",
                        "model": "gpt-4",
                        "response_content": "Let me calculate",
                        "tokens_input": 50,
                        "tokens_output": 20,
                        "tool_calls_requested": [
                            {
                                "tool_call_id": "c1",
                                "tool_name": "calculator",
                                "arguments": {"expression": "2+2"},
                            }
                        ],
                    },
                },
                {
                    "step_index": 1,
                    "step_type": "tool_call",
                    "tool_call": {
                        "tool_call_id": "c1",
                        "tool_name": "calculator",
                        "arguments": {"expression": "2+2"},
                        "result": "4",
                        "is_error": False,
                        "latency_ms": 5,
                    },
                    "content": "4",
                },
                {
                    "step_index": 2,
                    "step_type": "final_answer",
                    "content": "The answer is 4",
                },
            ],
            metrics={
                "total_steps": 3,
                "llm_calls": 1,
                "tool_calls": 1,
                "tool_results": 1,
                "errors": 0,
                "total_tokens_input": 50,
                "total_tokens_output": 20,
                "total_cost_usd": 0.005,
                "total_duration_ms": 200,
                "unique_tools_used": ["calculator"],
                "tool_error_rate": 0.0,
                "average_llm_latency_ms": 100.0,
                "average_tool_latency_ms": 5.0,
            },
        )

    def test_trajectory_completeness_completed(self) -> None:
        metric = TrajectoryCompletenessMetric()
        traj = self._make_completed_trajectory()
        result = _run_async(metric.evaluate(MetricInput(metadata={"trajectory": traj})))
        assert result.is_success
        assert result.normalized_score == 1.0

    def test_trajectory_completeness_max_steps(self) -> None:
        metric = TrajectoryCompletenessMetric()
        traj = _build_trajectory_dict(
            status="max_steps_reached",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "llm_call",
                    "content": "thinking",
                },
            ],
        )
        result = _run_async(metric.evaluate(MetricInput(metadata={"trajectory": traj})))
        assert result.is_success
        assert 0.0 < result.normalized_score < 1.0

    def test_trajectory_completeness_no_trajectory(self) -> None:
        metric = TrajectoryCompletenessMetric()
        result = _run_async(metric.evaluate(MetricInput()))
        assert not result.is_success

    def test_trajectory_efficiency_good(self) -> None:
        metric = TrajectoryEfficiencyMetric()
        traj = self._make_completed_trajectory()
        result = _run_async(metric.evaluate(MetricInput(metadata={"trajectory": traj})))
        assert result.is_success
        assert result.normalized_score > 0.5

    def test_trajectory_efficiency_errors(self) -> None:
        metric = TrajectoryEfficiencyMetric()
        traj = _build_trajectory_dict(
            status="completed",
            metrics={
                "total_steps": 20,
                "tool_calls": 2,
                "llm_calls": 10,
                "errors": 8,
                "tool_error_rate": 0.9,
            },
        )
        result = _run_async(metric.evaluate(MetricInput(metadata={"trajectory": traj})))
        assert result.is_success
        assert result.normalized_score < 0.5

    def test_trajectory_error_recovery_full(self) -> None:
        metric = TrajectoryErrorRecoveryMetric()
        traj = _build_trajectory_dict(
            status="completed",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "tool_call",
                    "tool_call": {
                        "tool_call_id": "c1",
                        "tool_name": "failing_tool",
                        "is_error": True,
                        "result": "",
                    },
                },
                {
                    "step_index": 1,
                    "step_type": "llm_call",
                    "content": "That failed, let me try another approach",
                    "llm_call": {
                        "provider": "openai",
                        "model": "gpt-4",
                        "response_content": "trying alternative",
                        "tool_calls_requested": [],
                    },
                },
                {
                    "step_index": 2,
                    "step_type": "final_answer",
                    "content": "Here is my answer despite the error",
                },
            ],
            metrics={
                "total_steps": 3,
                "errors": 1,
                "tool_calls": 1,
                "tool_error_rate": 1.0,
            },
        )
        result = _run_async(metric.evaluate(MetricInput(metadata={"trajectory": traj})))
        assert result.is_success
        assert result.normalized_score > 0.5

    def test_trajectory_error_recovery_none(self) -> None:
        metric = TrajectoryErrorRecoveryMetric()
        traj = _build_trajectory_dict(
            status="completed",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "final_answer",
                    "content": "Done",
                },
            ],
            metrics={
                "total_steps": 1,
                "errors": 0,
                "tool_calls": 0,
            },
        )
        result = _run_async(metric.evaluate(MetricInput(metadata={"trajectory": traj})))
        assert result.is_success
        assert result.normalized_score == 1.0

    def test_trajectory_tool_selection_valid(self) -> None:
        metric = TrajectoryToolSelectionMetric()
        traj = _build_trajectory_dict(
            status="completed",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "tool_call",
                    "tool_call": {
                        "tool_call_id": "c1",
                        "tool_name": "calculator",
                        "arguments": {"expression": "1+1"},
                        "result": "2",
                    },
                },
                {
                    "step_index": 1,
                    "step_type": "tool_call",
                    "tool_call": {
                        "tool_call_id": "c2",
                        "tool_name": "lookup",
                        "arguments": {"query": "python"},
                        "result": "Python info",
                    },
                },
            ],
            metrics={
                "total_steps": 2,
                "unique_tools_used": ["calculator", "lookup"],
            },
        )
        result = _run_async(
            metric.evaluate(
                MetricInput(
                    metadata={
                        "trajectory": traj,
                        "available_tools": ["calculator", "lookup"],
                    }
                )
            )
        )
        assert result.is_success
        assert result.normalized_score >= 0.7

    def test_trajectory_tool_selection_invalid(self) -> None:
        metric = TrajectoryToolSelectionMetric()
        traj = _build_trajectory_dict(
            status="completed",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "tool_call",
                    "tool_call": {
                        "tool_call_id": "c1",
                        "tool_name": "nonexistent_tool",
                        "arguments": {},
                        "result": "",
                        "is_error": True,
                    },
                },
            ],
            metrics={
                "total_steps": 1,
                "unique_tools_used": ["nonexistent_tool"],
            },
        )
        result = _run_async(
            metric.evaluate(
                MetricInput(
                    metadata={
                        "trajectory": traj,
                        "available_tools": ["calculator", "lookup"],
                    }
                )
            )
        )
        assert result.is_success
        assert result.normalized_score < 0.5


# ---------------------------------------------------------------------------
# Integration tests — TrajectoryEvaluator (synchronous wrappers)
# ---------------------------------------------------------------------------


class TestTrajectoryEvaluator:
    """Integration tests for the trajectory evaluator."""

    def test_evaluator_initialization(self) -> None:
        evaluator = TrajectoryEvaluator()
        _run_async(evaluator.initialize())
        metrics = evaluator.get_available_metrics()
        assert "trajectory_completeness" in metrics
        assert "trajectory_efficiency" in metrics
        assert "trajectory_error_recovery" in metrics
        assert "trajectory_tool_selection" in metrics

    def test_evaluate_completed_trajectory(self) -> None:
        evaluator = TrajectoryEvaluator()
        _run_async(evaluator.initialize())

        traj = _build_trajectory_dict(
            status="completed",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "llm_call",
                    "content": "I'll calculate",
                    "llm_call": {
                        "provider": "openai",
                        "model": "gpt-4",
                        "response_content": "I'll calculate",
                        "tokens_input": 50,
                        "tokens_output": 20,
                        "tool_calls_requested": [
                            {
                                "tool_call_id": "c1",
                                "tool_name": "calculator",
                                "arguments": {"expression": "2+2"},
                            }
                        ],
                    },
                },
                {
                    "step_index": 1,
                    "step_type": "tool_call",
                    "tool_call": {
                        "tool_call_id": "c1",
                        "tool_name": "calculator",
                        "arguments": {"expression": "2+2"},
                        "result": "4",
                        "is_error": False,
                        "latency_ms": 5,
                    },
                    "content": "4",
                },
                {
                    "step_index": 2,
                    "step_type": "final_answer",
                    "content": "The answer is 4",
                },
            ],
            metrics={
                "total_steps": 3,
                "llm_calls": 1,
                "tool_calls": 1,
                "tool_results": 1,
                "errors": 0,
                "total_tokens_input": 50,
                "total_tokens_output": 20,
                "total_cost_usd": 0.005,
                "total_duration_ms": 200,
                "unique_tools_used": ["calculator"],
                "tool_error_rate": 0.0,
                "average_llm_latency_ms": 100.0,
                "average_tool_latency_ms": 5.0,
            },
        )

        result = _run_async(
            evaluator.evaluate_trajectory(
                traj,
                prompt="Calculate 2+2",
                available_tools=("calculator", "lookup"),
            )
        )

        assert isinstance(result, TrajectoryEvaluationResult)
        assert result.trajectory_id == "test-traj-001"
        assert result.run_id == "test-run-001"
        assert len(result.metric_results) == 4
        assert all(r.is_success for r in result.metric_results)
        assert result.overall_score > 0.5
        assert result.passed

    def test_evaluate_failed_trajectory(self) -> None:
        evaluator = TrajectoryEvaluator()
        _run_async(evaluator.initialize())

        traj = _build_trajectory_dict(
            status="failed",
            steps=[
                {
                    "step_index": 0,
                    "step_type": "error",
                    "error": "Provider timeout",
                },
            ],
            metrics={
                "total_steps": 1,
                "errors": 1,
                "tool_calls": 0,
                "llm_calls": 0,
            },
        )

        result = _run_async(
            evaluator.evaluate_trajectory(
                traj,
                prompt="Do something",
            )
        )

        assert not result.passed
        assert result.overall_score < 0.5


# ---------------------------------------------------------------------------
# Integration test — Full trajectory lifecycle (THE B.6 PROOF)
# ---------------------------------------------------------------------------


class TestFullTrajectoryLifecycle:
    """Proves the complete B.6 path:
    AGENT TASK → AGENT EXECUTION → MODEL ACTION → TOOL CALL →
    TOOL RESULT → NEXT ACTION → FINAL RESPONSE → COMPLETE TRAJECTORY →
    TRAJECTORY METRICS → PERSISTED EVALUATION RESULT
    """

    def test_complete_trajectory_lifecycle(self) -> None:
        """
        Simulates a full agent trajectory from task to evaluation.
        The agent receives a task, uses tools, produces a final answer,
        and the trajectory is evaluated with metrics.
        """
        registry = _build_test_tool_registry()

        recorder = TrajectoryRecorder(
            run_id="integration-run-001",
            agent_name="calculator_agent",
            task_description="Calculate 15 * 7 + 3",
        )

        # Step 1: LLM decides to use calculator
        recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=2,
            response_content="I'll calculate 15 * 7 + 3 using the calculator",
            tokens_input=80,
            tokens_output=30,
            cost_usd=0.003,
            latency_ms=150,
            tool_calls_requested=(
                ToolCallRecord(
                    tool_call_id="call-001",
                    tool_name="calculator",
                    arguments={"expression": "15 * 7 + 3"},
                ),
            ),
        )

        # Step 2: Tool executes
        executor = SafeToolExecutor(registry)
        tool_result = executor.execute("calculator", {"expression": "15 * 7 + 3"})
        recorder.record_tool_call(
            tool_call_id="call-001",
            tool_name="calculator",
            arguments={"expression": "15 * 7 + 3"},
            result=tool_result.result,
            is_error=tool_result.is_error,
            latency_ms=tool_result.latency_ms,
        )

        # Step 3: LLM produces final answer
        recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=4,
            response_content=f"The result is {tool_result.result}",
            tokens_input=110,
            tokens_output=15,
            cost_usd=0.002,
            latency_ms=100,
        )
        recorder.record_final_answer(f"15 * 7 + 3 = {tool_result.result}")

        # Build trajectory
        trajectory = recorder.build()

        assert trajectory.run_id == "integration-run-001"
        assert trajectory.agent_name == "calculator_agent"
        assert trajectory.step_count == 4
        assert trajectory.is_success
        assert trajectory.final_response == "15 * 7 + 3 = 108"
        assert trajectory.metrics.tool_calls == 1
        assert trajectory.metrics.llm_calls == 2
        assert trajectory.metrics.errors == 0

        # Evaluate trajectory
        evaluator = TrajectoryEvaluator()
        _run_async(evaluator.initialize())

        evaluation = _run_async(
            evaluator.evaluate_trajectory_object(
                trajectory,
                prompt="Calculate 15 * 7 + 3",
                reference="108",
                available_tools=("calculator", "lookup"),
            )
        )

        assert isinstance(evaluation, TrajectoryEvaluationResult)
        assert evaluation.trajectory_id == trajectory.trajectory_id
        assert evaluation.run_id == "integration-run-001"
        assert len(evaluation.metric_results) == 4
        assert all(r.is_success for r in evaluation.metric_results)
        assert evaluation.overall_score > 0.5
        assert evaluation.passed

        scores = evaluation.metric_scores
        assert "trajectory_completeness" in scores
        assert scores["trajectory_completeness"] == 1.0
        assert scores["trajectory_efficiency"] > 0.5
        assert scores["trajectory_error_recovery"] == 1.0
        assert scores["trajectory_tool_selection"] > 0.5

        # Verify trajectory serialization (simulates persistence)
        traj_dict = trajectory.to_dict()
        restored = AgentTrajectory.from_dict(traj_dict)
        assert restored.trajectory_id == trajectory.trajectory_id
        assert restored.step_count == trajectory.step_count
        assert restored.final_response == trajectory.final_response

    def test_trajectory_with_tool_failure_and_recovery(self) -> None:
        """
        Proves error recovery in the trajectory evaluation path.
        Agent tries a tool, it fails, agent recovers and succeeds.
        """
        registry = _build_test_tool_registry()

        recorder = TrajectoryRecorder(
            run_id="recovery-run-001",
            agent_name="resilient_agent",
            task_description="Calculate something that might fail",
        )

        # Step 1: LLM calls a failing tool
        recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=2,
            response_content="Let me try the failing tool",
            tokens_input=60,
            tokens_output=25,
            latency_ms=130,
            tool_calls_requested=(
                ToolCallRecord(
                    tool_call_id="call-fail-1",
                    tool_name="failing_tool",
                    arguments={"reason": "test failure"},
                ),
            ),
        )

        # Step 2: Tool fails
        executor = SafeToolExecutor(registry)
        fail_result = executor.execute("failing_tool", {"reason": "test failure"})
        recorder.record_tool_call(
            tool_call_id="call-fail-1",
            tool_name="failing_tool",
            arguments={"reason": "test failure"},
            result=fail_result.result,
            is_error=True,
            latency_ms=5,
        )

        # Step 3: LLM recovers — uses calculator instead
        recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=4,
            response_content="That failed. Let me use the calculator instead",
            tokens_input=90,
            tokens_output=30,
            latency_ms=140,
            tool_calls_requested=(
                ToolCallRecord(
                    tool_call_id="call-retry-1",
                    tool_name="calculator",
                    arguments={"expression": "42"},
                ),
            ),
        )

        # Step 4: Calculator succeeds
        calc_result = executor.execute("calculator", {"expression": "42"})
        recorder.record_tool_call(
            tool_call_id="call-retry-1",
            tool_name="calculator",
            arguments={"expression": "42"},
            result=calc_result.result,
            latency_ms=3,
        )

        # Step 5: Final answer
        recorder.record_final_answer("The answer is 42")

        trajectory = recorder.build()

        assert trajectory.step_count == 5
        assert trajectory.metrics.errors == 0
        assert trajectory.metrics.tool_calls == 2

        # Evaluate
        evaluator = TrajectoryEvaluator()
        _run_async(evaluator.initialize())

        evaluation = _run_async(
            evaluator.evaluate_trajectory_object(
                trajectory,
                prompt="Calculate something",
                available_tools=("calculator", "lookup", "failing_tool"),
            )
        )

        assert evaluation.passed
        scores = evaluation.metric_scores
        assert scores["trajectory_error_recovery"] >= 0.5
        assert scores["trajectory_completeness"] == 1.0

    def test_trajectory_serialization_persistence_evaluation(self) -> None:
        """
        Proves trajectory can be serialized, persisted (simulated),
        deserialized, and evaluated — the full persistence path.
        """
        recorder = TrajectoryRecorder(
            run_id="persist-run-001",
            agent_name="persist_agent",
        )

        recorder.record_llm_call(
            provider="openai",
            model="gpt-4",
            messages_sent=1,
            response_content="Searching for info",
            tokens_input=40,
            tokens_output=15,
            latency_ms=90,
            tool_calls_requested=(
                ToolCallRecord(
                    tool_call_id="c1",
                    tool_name="lookup",
                    arguments={"query": "python"},
                ),
            ),
        )
        recorder.record_tool_call(
            tool_call_id="c1",
            tool_name="lookup",
            arguments={"query": "python"},
            result="Python is a programming language",
            latency_ms=3,
        )
        recorder.record_final_answer("Python is a programming language")

        trajectory = recorder.build()

        # Serialize (simulates DB persistence)
        persisted_data = trajectory.to_dict()

        # Deserialize (simulates loading from DB)
        loaded = AgentTrajectory.from_dict(persisted_data)

        # Evaluate the loaded trajectory
        evaluator = TrajectoryEvaluator()
        _run_async(evaluator.initialize())

        evaluation = _run_async(
            evaluator.evaluate_trajectory_object(
                loaded,
                prompt="What is Python?",
            )
        )

        assert evaluation.passed
        assert len(evaluation.metric_results) == 4
        assert all(r.is_success for r in evaluation.metric_results)
