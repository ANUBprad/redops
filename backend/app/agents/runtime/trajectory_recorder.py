"""Trajectory recorder for agent execution.

Records every LLM call, tool invocation, tool result, and reasoning
step during agent execution. Produces an immutable AgentTrajectory
for evaluation and replay.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.agents.domain.trajectory import (
    AgentTrajectory,
    LLMCallRecord,
    ToolCallRecord,
    TrajectoryStatus,
    TrajectoryStep,
    TrajectoryStepType,
    compute_trajectory_metrics,
)


class TrajectoryRecorder:
    """Records agent execution steps and builds the final trajectory.

    Thread-safe via sequential append (asyncio single-thread model).
    The recorder accumulates steps and produces an immutable
    AgentTrajectory on finalization.
    """

    def __init__(
        self,
        run_id: str,
        agent_name: str = "",
        task_description: str = "",
    ) -> None:
        self._run_id = run_id
        self._agent_name = agent_name
        self._task_description = task_description
        self._steps: list[TrajectoryStep] = []
        self._conversation_history: list[dict[str, Any]] = []
        self._status = TrajectoryStatus.COMPLETED
        self._error: str | None = None
        self._started_at = datetime.now(UTC)
        self._completed_at: datetime | None = None
        self._metadata: dict[str, Any] = {}
        self._step_counter = 0

    def record_llm_call(
        self,
        *,
        provider: str,
        model: str,
        messages_sent: int,
        response_content: str,
        tool_calls_requested: tuple[ToolCallRecord, ...] = (),
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
        latency_ms: int = 0,
        finish_reason: str = "",
        reasoning: str = "",
    ) -> TrajectoryStep:
        """Record an LLM provider call as a trajectory step."""
        llm_call = LLMCallRecord(
            provider=provider,
            model=model,
            messages_sent=messages_sent,
            response_content=response_content,
            tool_calls_requested=tool_calls_requested,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            completed_at=datetime.now(UTC),
        )
        step = TrajectoryStep(
            step_index=self._step_counter,
            step_type=TrajectoryStepType.LLM_CALL,
            llm_call=llm_call,
            content=response_content,
            reasoning=reasoning,
            timestamp=datetime.now(UTC),
        )
        self._steps.append(step)
        self._step_counter += 1

        self._conversation_history.append(
            {
                "role": "assistant",
                "content": response_content,
                "tool_calls": [
                    {
                        "id": tc.tool_call_id,
                        "name": tc.tool_name,
                        "arguments": tc.arguments,
                    }
                    for tc in tool_calls_requested
                ]
                if tool_calls_requested
                else [],
            }
        )

        return step

    def record_tool_call(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: str = "",
        is_error: bool = False,
        latency_ms: int = 0,
    ) -> TrajectoryStep:
        """Record a tool execution as a trajectory step."""
        tool_call = ToolCallRecord(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            is_error=is_error,
            latency_ms=latency_ms,
            completed_at=datetime.now(UTC),
        )
        step = TrajectoryStep(
            step_index=self._step_counter,
            step_type=TrajectoryStepType.TOOL_CALL,
            tool_call=tool_call,
            content=result,
            timestamp=datetime.now(UTC),
        )
        self._steps.append(step)
        self._step_counter += 1

        self._conversation_history.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            }
        )

        return step

    def record_tool_result(
        self,
        *,
        tool_call_id: str,
        tool_name: str,
        result: str,
        is_error: bool = False,
        latency_ms: int = 0,
    ) -> TrajectoryStep:
        """Record a tool result (alias for record_tool_call with result focus)."""
        return self.record_tool_call(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments={},
            result=result,
            is_error=is_error,
            latency_ms=latency_ms,
        )

    def record_reasoning(
        self,
        content: str,
        *,
        reasoning: str = "",
    ) -> TrajectoryStep:
        """Record an intermediate reasoning step."""
        step = TrajectoryStep(
            step_index=self._step_counter,
            step_type=TrajectoryStepType.REASONING,
            content=content,
            reasoning=reasoning,
            timestamp=datetime.now(UTC),
        )
        self._steps.append(step)
        self._step_counter += 1
        return step

    def record_final_answer(
        self,
        content: str,
    ) -> TrajectoryStep:
        """Record the final answer/response."""
        step = TrajectoryStep(
            step_index=self._step_counter,
            step_type=TrajectoryStepType.FINAL_ANSWER,
            content=content,
            timestamp=datetime.now(UTC),
        )
        self._steps.append(step)
        self._step_counter += 1

        self._conversation_history.append(
            {
                "role": "assistant",
                "content": content,
            }
        )

        return step

    def record_error(self, error: str) -> TrajectoryStep:
        """Record an error step."""
        step = TrajectoryStep(
            step_index=self._step_counter,
            step_type=TrajectoryStepType.ERROR,
            error=error,
            timestamp=datetime.now(UTC),
        )
        self._steps.append(step)
        self._step_counter += 1
        return step

    def set_status(self, status: TrajectoryStatus) -> None:
        """Set the terminal status of the trajectory."""
        self._status = status

    def set_error(self, error: str) -> None:
        """Set the error message and status."""
        self._error = error
        self._status = TrajectoryStatus.FAILED

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata entry."""
        self._metadata[key] = value

    def build(self) -> AgentTrajectory:
        """Build the immutable trajectory from recorded steps."""
        self._completed_at = datetime.now(UTC)
        steps = tuple(self._steps)
        metrics = compute_trajectory_metrics(steps)

        return AgentTrajectory(
            trajectory_id=str(uuid.uuid4()),
            run_id=self._run_id,
            agent_name=self._agent_name,
            task_description=self._task_description,
            status=self._status,
            steps=steps,
            metrics=metrics,
            conversation_history=tuple(self._conversation_history),
            started_at=self._started_at,
            completed_at=self._completed_at,
            error=self._error,
            metadata=self._metadata,
        )

    @property
    def step_count(self) -> int:
        return len(self._steps)

    @property
    def is_recording(self) -> bool:
        return True
