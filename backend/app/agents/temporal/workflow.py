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
        FailAgentRunInput,
        ProgressInput,
        RunIdInput,
        StartAgentRunInput,
        cancel_agent_run_activity,
        complete_agent_run_activity,
        fail_agent_run_activity,
        queue_agent_run_activity,
        start_agent_run_activity,
        update_agent_run_progress_activity,
    )


@dataclass(frozen=True, slots=True)
class AgentRunWorkflowInput:
    """Input for the agent run workflow."""

    run_id: str
    total_steps: int = 0


@dataclass(frozen=True, slots=True)
class AgentRunWorkflowResult:
    """Result of the agent run workflow."""

    run_id: str
    status: str
    steps_completed: int = 0
    steps_total: int = 0


@workflow.defn
class AgentRunWorkflow:
    """Workflow that orchestrates an agent run's lifecycle.

    Handles queuing, starting, progress tracking, and completion
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
            StartAgentRunInput(run_id=input.run_id, total_steps=input.total_steps),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        steps_completed = 0
        steps_failed = 0

        for _step_index in range(input.total_steps):
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
                    steps_completed=steps_completed,
                    steps_total=input.total_steps,
                )

            try:
                steps_completed += 1
                await workflow.execute_activity(
                    update_agent_run_progress_activity,
                    ProgressInput(
                        run_id=input.run_id,
                        steps_completed=steps_completed,
                        steps_failed=steps_failed,
                    ),
                    start_to_close_timeout=activity_start_to_close,
                    schedule_to_close_timeout=activity_schedule_to_close,
                )
            except Exception:
                steps_failed += 1
                steps_completed += 1
                await workflow.execute_activity(
                    update_agent_run_progress_activity,
                    ProgressInput(
                        run_id=input.run_id,
                        steps_completed=steps_completed,
                        steps_failed=steps_failed,
                    ),
                    start_to_close_timeout=activity_start_to_close,
                    schedule_to_close_timeout=activity_schedule_to_close,
                )

        if steps_failed == input.total_steps:
            await workflow.execute_activity(
                fail_agent_run_activity,
                FailAgentRunInput(
                    run_id=input.run_id,
                    error_code="ALL_STEPS_FAILED",
                    error_message="All steps failed during execution",
                ),
                start_to_close_timeout=activity_start_to_close,
                schedule_to_close_timeout=activity_schedule_to_close,
            )
            return AgentRunWorkflowResult(
                run_id=input.run_id,
                status="failed",
                steps_completed=steps_completed,
                steps_total=input.total_steps,
            )

        await workflow.execute_activity(
            complete_agent_run_activity,
            RunIdInput(run_id=input.run_id),
            start_to_close_timeout=activity_start_to_close,
            schedule_to_close_timeout=activity_schedule_to_close,
        )

        return AgentRunWorkflowResult(
            run_id=input.run_id,
            status="completed",
            steps_completed=steps_completed,
            steps_total=input.total_steps,
        )
