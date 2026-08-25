"""Temporal workflow for agent run execution.

Orchestrates the full lifecycle of an agent run:
CREATED → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED.

The workflow calls activities that delegate to existing CQRS
handlers, ensuring no duplicate business logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.agents.temporal.activities import (
        CancelAgentRunInput,
        ExecuteAgentLoopInput,
        ExecuteAgentLoopResult,
        FailAgentRunInput,
        RunIdInput,
        StartAgentRunInput,
        cancel_agent_run_activity,
        execute_agent_loop_activity,
        fail_agent_run_activity,
        queue_agent_run_activity,
        start_agent_run_activity,
    )


@dataclass(frozen=True, slots=True)
class AgentRunWorkflowInput:
    """Input for the agent run workflow."""

    run_id: str
    provider_name: str = ""
    model_id: str = ""
    system_prompt: str = ""
    tools: tuple[str, ...] = ()
    max_steps: int = 10


@dataclass(frozen=True, slots=True)
class AgentRunWorkflowResult:
    """Result of the agent run workflow."""

    run_id: str
    status: str
    total_steps: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0


@workflow.defn
class AgentRunWorkflow:
    """Workflow that orchestrates an agent run's lifecycle.

    Handles queuing, starting, agent loop execution, and completion
    of an agent run. Supports cancellation via signal.
    """

    def __init__(self) -> None:
        self._cancel_requested: bool = False

    @workflow.signal
    def cancel(self) -> None:
        self._cancel_requested = True

    @workflow.run
    async def run(
        self,
        input: AgentRunWorkflowInput,
    ) -> AgentRunWorkflowResult:
        activity_start_to_close = timedelta(seconds=30)
        activity_schedule_to_close = timedelta(minutes=5)

        await workflow.execute_activity(
            queue_agent_run_activity,
            RunIdInput(run_id=input.run_id),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        await workflow.execute_activity(
            start_agent_run_activity,
            StartAgentRunInput(run_id=input.run_id, total_steps=input.max_steps),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        if self._cancel_requested:
            await workflow.execute_activity(
                cancel_agent_run_activity,
                CancelAgentRunInput(
                    run_id=input.run_id,
                    reason="user_cancelled",
                    force=True,
                ),
                start_to_close_timeout=activity_start_to_close,
                schedule_to_close_timeout=activity_schedule_to_close,
            )
            return AgentRunWorkflowResult(
                run_id=input.run_id,
                status="cancelled",
            )

        loop_result: ExecuteAgentLoopResult = await workflow.execute_activity(
            execute_agent_loop_activity,
            ExecuteAgentLoopInput(
                run_id=input.run_id,
                provider_name=input.provider_name,
                model_id=input.model_id,
                system_prompt=input.system_prompt,
                tools=input.tools,
                max_steps=input.max_steps,
            ),
            start_to_close_timeout=timedelta(minutes=10),
            schedule_to_close_timeout=timedelta(minutes=15),
        )

        if not loop_result.success:
            await workflow.execute_activity(
                fail_agent_run_activity,
                FailAgentRunInput(
                    run_id=input.run_id,
                    error_code="EXECUTION_FAILED",
                    error_message=loop_result.error or "Agent loop failed",
                ),
                start_to_close_timeout=activity_start_to_close,
                schedule_to_close_timeout=activity_schedule_to_close,
            )
            return AgentRunWorkflowResult(
                run_id=input.run_id,
                status="failed",
                total_steps=loop_result.total_steps,
                total_tokens_input=loop_result.total_tokens_input,
                total_tokens_output=loop_result.total_tokens_output,
                total_cost_usd=loop_result.total_cost_usd,
                total_duration_ms=loop_result.total_duration_ms,
            )

        return AgentRunWorkflowResult(
            run_id=input.run_id,
            status="completed",
            total_steps=loop_result.total_steps,
            total_llm_calls=loop_result.total_llm_calls,
            total_tool_calls=loop_result.total_tool_calls,
            total_tokens_input=loop_result.total_tokens_input,
            total_tokens_output=loop_result.total_tokens_output,
            total_cost_usd=loop_result.total_cost_usd,
            total_duration_ms=loop_result.total_duration_ms,
        )
