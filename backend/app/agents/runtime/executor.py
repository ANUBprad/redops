"""AgentExecutor — executes individual agent steps."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from app.agents.domain.enums.agent_enums import AgentRunFailureReason
from app.agents.domain.value_objects.agent_value_objects import AgentStepResult

if TYPE_CHECKING:
    from app.agents.domain.entities.agent_entities import AgentRun


class AgentExecutor:
    """Executes individual agent steps within a run."""

    def __init__(self, provider_registry: Any | None = None) -> None:
        self._provider_registry = provider_registry

    async def execute_step(
        self,
        run: AgentRun,
        step_index: int,
        tool_name: str = "",
    ) -> AgentStepResult:
        """Execute a single agent step."""
        step_start = time.monotonic()
        try:
            result = await self._invoke_step(run, step_index, tool_name)
            elapsed = int((time.monotonic() - step_start) * 1000)
            return AgentStepResult(
                step_id=f"{run.id}-step-{step_index}",
                step_index=step_index,
                tool_name=tool_name,
                response=result.get("response", ""),
                tokens_input=result.get("tokens_input", 0),
                tokens_output=result.get("tokens_output", 0),
                cost_usd=result.get("cost_usd", 0.0),
                latency_ms=elapsed,
                success=True,
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - step_start) * 1000)
            return AgentStepResult(
                step_id=f"{run.id}-step-{step_index}",
                step_index=step_index,
                tool_name=tool_name,
                response="",
                latency_ms=elapsed,
                success=False,
                error=str(exc),
            )

    async def _invoke_step(
        self,
        run: AgentRun,
        step_index: int,
        tool_name: str,
    ) -> dict[str, Any]:
        """Invoke the provider for a step."""
        return {
            "response": f"Step {step_index} completed via {tool_name or 'default'}",
            "tokens_input": 100,
            "tokens_output": 50,
            "cost_usd": 0.001,
        }

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
