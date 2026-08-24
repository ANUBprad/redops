"""Domain model for agent execution trajectories.

Defines the trajectory aggregate: a complete record of an agent's
execution path including tool calls, tool results, model responses,
and intermediate reasoning. The trajectory is the fundamental unit
for agent evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique
from typing import Any


@unique
class TrajectoryStepType(Enum):
    """Type of a single step in the trajectory."""

    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REASONING = "reasoning"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"


@unique
class TrajectoryStatus(Enum):
    """Terminal status of a trajectory."""

    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BUDGET_EXHAUSTED = "budget_exhausted"
    MAX_STEPS_REACHED = "max_steps_reached"
    CANCELLED = "cancelled"

    @property
    def is_success(self) -> bool:
        return self == TrajectoryStatus.COMPLETED

    @property
    def is_terminal(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """A single tool call executed during the trajectory.

    Captures the full lifecycle: model requested a call, the call was
    executed, and the result was returned.
    """

    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result: str = ""
    is_error: bool = False
    latency_ms: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def duration_ms(self) -> int:
        if self.completed_at is None:
            return self.latency_ms
        return int((self.completed_at - self.started_at).total_seconds() * 1000)


@dataclass(frozen=True, slots=True)
class LLMCallRecord:
    """A single LLM provider call during the trajectory."""

    provider: str = ""
    model: str = ""
    messages_sent: int = 0
    response_content: str = ""
    tool_calls_requested: tuple[ToolCallRecord, ...] = ()
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    """A single step in the agent trajectory.

    Each step is an atomic unit of work: either an LLM call, a tool
    execution, or a reasoning transition. Steps are ordered by index.
    """

    step_index: int
    step_type: TrajectoryStepType
    llm_call: LLMCallRecord | None = None
    tool_call: ToolCallRecord | None = None
    content: str = ""
    reasoning: str = ""
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_error(self) -> bool:
        return self.error is not None or self.step_type == TrajectoryStepType.ERROR

    @property
    def tokens_used(self) -> int:
        if self.llm_call is not None:
            return self.llm_call.tokens_input + self.llm_call.tokens_output
        return 0

    @property
    def cost_usd(self) -> float:
        if self.llm_call is not None:
            return self.llm_call.cost_usd
        return 0.0


@dataclass(frozen=True, slots=True)
class TrajectoryMetrics:
    """Aggregated metrics computed from a trajectory."""

    total_steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    tool_results: int = 0
    errors: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    unique_tools_used: tuple[str, ...] = ()
    tool_error_rate: float = 0.0
    average_llm_latency_ms: float = 0.0
    average_tool_latency_ms: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.total_tokens_input + self.total_tokens_output

    @property
    def steps_per_tool_call(self) -> float:
        if self.tool_calls == 0:
            return 0.0
        return self.total_steps / self.tool_calls

    @property
    def error_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.errors / self.total_steps


@dataclass(frozen=True, slots=True)
class AgentTrajectory:
    """Complete execution trajectory of an agent.

    The trajectory captures the full execution path: every LLM call,
    every tool invocation, every tool result, and every intermediate
    reasoning step. This is the primary input for trajectory evaluation.

    The trajectory is immutable once built — it represents a historical
    record of what actually happened during agent execution.
    """

    trajectory_id: str
    run_id: str
    agent_name: str = ""
    task_description: str = ""
    status: TrajectoryStatus = TrajectoryStatus.COMPLETED
    steps: tuple[TrajectoryStep, ...] = ()
    metrics: TrajectoryMetrics = field(default_factory=TrajectoryMetrics)
    conversation_history: tuple[dict[str, Any], ...] = ()
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    @property
    def duration_ms(self) -> int:
        if self.completed_at is None:
            return 0
        return int((self.completed_at - self.started_at).total_seconds() * 1000)

    @property
    def is_success(self) -> bool:
        return self.status.is_success

    @property
    def final_response(self) -> str:
        """Extract the final assistant response from the trajectory."""
        for step in reversed(self.steps):
            if step.step_type == TrajectoryStepType.FINAL_ANSWER:
                return step.content
            if (
                step.step_type == TrajectoryStepType.LLM_CALL
                and step.llm_call is not None
                and step.llm_call.tool_calls_requested == ()
            ):
                return step.llm_call.response_content
        return ""

    @property
    def all_tool_calls(self) -> tuple[ToolCallRecord, ...]:
        """Extract all tool calls from the trajectory."""
        calls: list[ToolCallRecord] = []
        for step in self.steps:
            if step.tool_call is not None:
                calls.append(step.tool_call)
            if step.llm_call is not None:
                calls.extend(step.llm_call.tool_calls_requested)
        return tuple(calls)

    @property
    def tool_names_used(self) -> tuple[str, ...]:
        """Return unique tool names used in the trajectory."""
        return self.metrics.unique_tools_used

    def get_steps_by_type(
        self,
        step_type: TrajectoryStepType,
    ) -> tuple[TrajectoryStep, ...]:
        """Filter steps by type."""
        return tuple(s for s in self.steps if s.step_type == step_type)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage or transport."""
        return {
            "trajectory_id": self.trajectory_id,
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "task_description": self.task_description,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "metadata": self.metadata,
            "conversation_history": self.conversation_history,
            "steps": [
                {
                    "step_index": s.step_index,
                    "step_type": s.step_type.value,
                    "content": s.content,
                    "reasoning": s.reasoning,
                    "error": s.error,
                    "timestamp": s.timestamp.isoformat(),
                    "llm_call": {
                        "provider": s.llm_call.provider,
                        "model": s.llm_call.model,
                        "messages_sent": s.llm_call.messages_sent,
                        "response_content": s.llm_call.response_content,
                        "tokens_input": s.llm_call.tokens_input,
                        "tokens_output": s.llm_call.tokens_output,
                        "cost_usd": s.llm_call.cost_usd,
                        "latency_ms": s.llm_call.latency_ms,
                        "finish_reason": s.llm_call.finish_reason,
                        "tool_calls_requested": [
                            {
                                "tool_call_id": tc.tool_call_id,
                                "tool_name": tc.tool_name,
                                "arguments": tc.arguments,
                                "result": tc.result,
                                "is_error": tc.is_error,
                                "latency_ms": tc.latency_ms,
                            }
                            for tc in s.llm_call.tool_calls_requested
                        ],
                    }
                    if s.llm_call
                    else None,
                    "tool_call": {
                        "tool_call_id": s.tool_call.tool_call_id,
                        "tool_name": s.tool_call.tool_name,
                        "arguments": s.tool_call.arguments,
                        "result": s.tool_call.result,
                        "is_error": s.tool_call.is_error,
                        "latency_ms": s.tool_call.latency_ms,
                    }
                    if s.tool_call
                    else None,
                }
                for s in self.steps
            ],
            "metrics": {
                "total_steps": self.metrics.total_steps,
                "llm_calls": self.metrics.llm_calls,
                "tool_calls": self.metrics.tool_calls,
                "tool_results": self.metrics.tool_results,
                "errors": self.metrics.errors,
                "total_tokens_input": self.metrics.total_tokens_input,
                "total_tokens_output": self.metrics.total_tokens_output,
                "total_cost_usd": self.metrics.total_cost_usd,
                "total_duration_ms": self.metrics.total_duration_ms,
                "unique_tools_used": list(self.metrics.unique_tools_used),
                "tool_error_rate": self.metrics.tool_error_rate,
                "average_llm_latency_ms": self.metrics.average_llm_latency_ms,
                "average_tool_latency_ms": self.metrics.average_tool_latency_ms,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentTrajectory:
        """Deserialize from dictionary."""
        steps_data = data.get("steps", [])
        steps = tuple(
            TrajectoryStep(
                step_index=s["step_index"],
                step_type=TrajectoryStepType(s["step_type"]),
                content=s.get("content", ""),
                reasoning=s.get("reasoning", ""),
                error=s.get("error"),
                timestamp=datetime.fromisoformat(s["timestamp"]),
                llm_call=LLMCallRecord(
                    provider=s["llm_call"]["provider"],
                    model=s["llm_call"]["model"],
                    messages_sent=s["llm_call"].get("messages_sent", 0),
                    response_content=s["llm_call"].get("response_content", ""),
                    tool_calls_requested=tuple(
                        ToolCallRecord(
                            tool_call_id=tc["tool_call_id"],
                            tool_name=tc["tool_name"],
                            arguments=tc.get("arguments", {}),
                            result=tc.get("result", ""),
                            is_error=tc.get("is_error", False),
                            latency_ms=tc.get("latency_ms", 0),
                        )
                        for tc in s["llm_call"].get("tool_calls_requested", [])
                    ),
                    tokens_input=s["llm_call"].get("tokens_input", 0),
                    tokens_output=s["llm_call"].get("tokens_output", 0),
                    cost_usd=s["llm_call"].get("cost_usd", 0.0),
                    latency_ms=s["llm_call"].get("latency_ms", 0),
                    finish_reason=s["llm_call"].get("finish_reason", ""),
                )
                if s.get("llm_call")
                else None,
                tool_call=ToolCallRecord(
                    tool_call_id=s["tool_call"]["tool_call_id"],
                    tool_name=s["tool_call"]["tool_name"],
                    arguments=s["tool_call"].get("arguments", {}),
                    result=s["tool_call"].get("result", ""),
                    is_error=s["tool_call"].get("is_error", False),
                    latency_ms=s["tool_call"].get("latency_ms", 0),
                )
                if s.get("tool_call")
                else None,
            )
            for s in steps_data
        )

        metrics_data = data.get("metrics", {})
        metrics = TrajectoryMetrics(
            total_steps=metrics_data.get("total_steps", 0),
            llm_calls=metrics_data.get("llm_calls", 0),
            tool_calls=metrics_data.get("tool_calls", 0),
            tool_results=metrics_data.get("tool_results", 0),
            errors=metrics_data.get("errors", 0),
            total_tokens_input=metrics_data.get("total_tokens_input", 0),
            total_tokens_output=metrics_data.get("total_tokens_output", 0),
            total_cost_usd=metrics_data.get("total_cost_usd", 0.0),
            total_duration_ms=metrics_data.get("total_duration_ms", 0),
            unique_tools_used=tuple(metrics_data.get("unique_tools_used", [])),
            tool_error_rate=metrics_data.get("tool_error_rate", 0.0),
            average_llm_latency_ms=metrics_data.get("average_llm_latency_ms", 0.0),
            average_tool_latency_ms=metrics_data.get("average_tool_latency_ms", 0.0),
        )

        return cls(
            trajectory_id=data["trajectory_id"],
            run_id=data["run_id"],
            agent_name=data.get("agent_name", ""),
            task_description=data.get("task_description", ""),
            status=TrajectoryStatus(data.get("status", "completed")),
            steps=steps,
            metrics=metrics,
            conversation_history=tuple(data.get("conversation_history", [])),
            started_at=datetime.fromisoformat(data["started_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


def compute_trajectory_metrics(steps: tuple[TrajectoryStep, ...]) -> TrajectoryMetrics:
    """Compute aggregated metrics from a sequence of trajectory steps."""
    if not steps:
        return TrajectoryMetrics()

    llm_calls = 0
    tool_calls = 0
    tool_results = 0
    errors = 0
    tokens_input = 0
    tokens_output = 0
    cost_usd = 0.0
    llm_latencies: list[int] = []
    tool_latencies: list[int] = []
    tools_used: set[str] = set()

    for step in steps:
        if step.is_error:
            errors += 1

        if step.llm_call is not None:
            llm_calls += 1
            tokens_input += step.llm_call.tokens_input
            tokens_output += step.llm_call.tokens_output
            cost_usd += step.llm_call.cost_usd
            llm_latencies.append(step.llm_call.latency_ms)
            for tc in step.llm_call.tool_calls_requested:
                tools_used.add(tc.tool_name)

        if step.tool_call is not None:
            tool_calls += 1
            tool_results += 1
            tool_latencies.append(step.tool_call.latency_ms)
            tools_used.add(step.tool_call.tool_name)

    total_duration = 0
    if steps:
        first_ts = steps[0].timestamp
        last_ts = steps[-1].timestamp
        total_duration = int((last_ts - first_ts).total_seconds() * 1000)

    tool_error_count = sum(
        1
        for step in steps
        if step.tool_call is not None and step.tool_call.is_error
    )
    tool_error_rate = tool_error_count / tool_calls if tool_calls > 0 else 0.0

    avg_llm = (
        sum(llm_latencies) / len(llm_latencies) if llm_latencies else 0.0
    )
    avg_tool = (
        sum(tool_latencies) / len(tool_latencies) if tool_latencies else 0.0
    )

    return TrajectoryMetrics(
        total_steps=len(steps),
        llm_calls=llm_calls,
        tool_calls=tool_calls,
        tool_results=tool_results,
        errors=errors,
        total_tokens_input=tokens_input,
        total_tokens_output=tokens_output,
        total_cost_usd=cost_usd,
        total_duration_ms=total_duration,
        unique_tools_used=tuple(sorted(tools_used)),
        tool_error_rate=tool_error_rate,
        average_llm_latency_ms=avg_llm,
        average_tool_latency_ms=avg_tool,
    )
