"""AgentRuntimeCoordinator — coordinates agent run execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.agents.domain.enums.agent_enums import AgentRunStatus
from app.agents.domain.tool_execution import ToolRegistry
from app.agents.runtime.checkpoint import AgentCheckpointManager
from app.agents.runtime.executor import AgentExecutor
from app.agents.runtime.planner import AgentPlanner

if TYPE_CHECKING:
    from app.agents.domain.contracts.agent_contracts import (
        AgentCheckpointRepository,
        AgentRunRepository,
    )
    from app.agents.domain.entities.agent_entities import AgentRun
    from app.providers.contracts.chat import ChatProvider
    from app.providers.contracts.tool_calling import ToolCallingProvider

logger = logging.getLogger(__name__)


class AgentRuntimeCoordinator:
    """Main coordinator for agent run execution.

    Coordinates planning, executing, checkpointing, and state management.
    Delegates actual AI execution to AgentExecutor → AgentLoop.
    """

    def __init__(
        self,
        run_repository: AgentRunRepository,
        checkpoint_repository: AgentCheckpointRepository,
        provider: ChatProvider | ToolCallingProvider,
        tool_registry: ToolRegistry | None = None,
        event_publisher: Any | None = None,
    ) -> None:
        self._run_repository = run_repository
        self._checkpoint_repository = checkpoint_repository
        self._event_publisher = event_publisher
        self._planner = AgentPlanner()
        self._executor = AgentExecutor(provider, tool_registry)
        self._checkpoint_manager = AgentCheckpointManager()

    async def execute_run(self, run: AgentRun) -> AgentExecutionOutcome:
        """Execute a complete agent run.

        Plans the run, then delegates to AgentExecutor which runs the
        full AgentLoop (LLM ↔ tool interaction) in one call.
        """
        if run.status == AgentRunStatus.CREATED:
            run.queue()
            await self._run_repository.save(run)

        try:
            plan = await self._planner.plan(run)
            validation_errors = await self._planner.validate_plan(plan)
            if validation_errors:
                run.fail(
                    error_code="PLAN_VALIDATION_FAILED",
                    error_message="; ".join(validation_errors),
                )
                await self._run_repository.save(run)
                return AgentExecutionOutcome(
                    success=False,
                    error=validation_errors[0],
                    steps_completed=run.steps_completed,
                    steps_total=run.steps_total,
                )

            run.start(plan.total_steps)
            await self._run_repository.save(run)

            result = self._executor.execute_run_sync(run)

            if result.success:
                run.record_step_success()
                run.record_token_usage(
                    result.total_tokens_input,
                    result.total_tokens_output,
                )
                run.record_cost(result.total_cost_usd)
                run.record_latency(result.total_duration_ms)
                run.complete()
            else:
                run.fail(
                    error_code="EXECUTION_FAILED",
                    error_message=result.error or "Agent loop failed",
                )

            await self._run_repository.save(run)
            return AgentExecutionOutcome(
                success=result.success,
                error=result.error,
                steps_completed=run.steps_completed,
                steps_total=run.steps_total,
                duration_ms=result.total_duration_ms,
            )

        except Exception as exc:
            logger.exception("Agent run execution failed")
            run.fail(
                error_code="EXECUTION_FAILED",
                error_message=str(exc),
            )
            await self._run_repository.save(run)
            return AgentExecutionOutcome(
                success=False,
                error=str(exc),
                steps_completed=run.steps_completed,
                steps_total=run.steps_total,
            )

    async def pause_run(self, run_id: Any) -> None:
        """Pause a running agent."""
        run = await self._run_repository.find_by_id(run_id)
        if run is None:
            msg = f"Agent run {run_id} not found"
            raise ValueError(msg)

        if run.status != AgentRunStatus.RUNNING:
            msg = f"Cannot pause run in {run.status.value} state"
            raise ValueError(msg)

        run._transition_to(AgentRunStatus.PAUSED)
        await self._run_repository.save(run)

    async def cancel_run(self, run_id: Any, *, force: bool = False) -> None:
        """Cancel a running agent."""
        run = await self._run_repository.find_by_id(run_id)
        if run is None:
            msg = f"Agent run {run_id} not found"
            raise ValueError(msg)

        if run.status.is_terminal:
            msg = f"Cannot cancel run in {run.status.value} state"
            raise ValueError(msg)

        from app.agents.domain.enums.agent_enums import AgentCancellationReason

        run.cancel(reason=AgentCancellationReason.USER_CANCELLED, force=force)
        await self._run_repository.save(run)


@dataclass(frozen=True, slots=True)
class AgentExecutionOutcome:
    """Result of an agent run execution."""

    success: bool = True
    error: str | None = None
    steps_completed: int = 0
    steps_total: int = 0
    duration_ms: int = 0
