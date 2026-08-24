"""AgentExecutor — executes agent runs via the AgentLoop.

Replaces the previous stub implementation with a real execution path
that delegates to AgentLoop for LLM ↔ tool interaction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.agents.domain.enums.agent_enums import AgentRunFailureReason
from app.agents.domain.tool_execution import ToolRegistry
from app.agents.runtime.agent_loop import AgentLoop, AgentLoopConfig, AgentLoopResult
from app.agents.runtime.trajectory_recorder import TrajectoryRecorder

if TYPE_CHECKING:
    from app.agents.domain.entities.agent_entities import AgentRun
    from app.providers.contracts.chat import ChatProvider
    from app.providers.contracts.tool_calling import ToolCallingProvider

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Executes agent runs using the AgentLoop.

    Provides the bridge between the CQRS/Temporal lifecycle layer
    and the actual LLM execution engine.
    """

    def __init__(
        self,
        provider: ChatProvider | ToolCallingProvider,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self._provider = provider
        self._tool_registry = tool_registry or ToolRegistry()

    def execute_run_sync(
        self,
        run: AgentRun,
        *,
        system_prompt: str = "",
        recorder: TrajectoryRecorder | None = None,
    ) -> AgentLoopResult:
        """Execute a complete agent run synchronously.

        This is the primary entry point used by AgentRuntimeCoordinator.
        Creates an AgentLoop configured from the run's parameters and
        executes the full LLM ↔ tool interaction loop.
        """
        config = AgentLoopConfig(
            max_steps=run.steps_total or run.config.max_steps,
            max_retries=run.config.max_retries,
            timeout_seconds=run.config.timeout_seconds,
            temperature=0.0,
            system_prompt=system_prompt,
        )

        loop = AgentLoop(
            provider=self._provider,
            tool_registry=self._tool_registry,
            config=config,
        )

        user_message = self._build_user_message(run)
        return loop.execute_sync(user_message, recorder=recorder)

    def classify_failure(self, error: str) -> AgentRunFailureReason:
        """Classify an error into a failure reason."""
        error_lower = error.lower()
        if "timeout" in error_lower:
            return AgentRunFailureReason.PROVIDER_TIMEOUT
        if "rate limit" in error_lower:
            return AgentRunFailureReason.RATE_LIMITED
        if "unavailable" in error_lower:
            return AgentRunFailureReason.PROVIDER_UNAVAILABLE
        if "auth" in error_lower:
            return AgentRunFailureReason.AUTHENTICATION_FAILED
        if "tool" in error_lower:
            return AgentRunFailureReason.TOOL_EXECUTION_ERROR
        return AgentRunFailureReason.INTERNAL_ERROR

    def _build_user_message(self, run: AgentRun) -> str:
        """Build the user message for the agent loop from run config."""
        parts: list[str] = []
        if run.agent_name:
            parts.append(f"Agent: {run.agent_name}")
        if run.config.tools:
            parts.append(f"Tools: {', '.join(run.config.tools)}")
        return "\n".join(parts) if parts else "Execute task"
