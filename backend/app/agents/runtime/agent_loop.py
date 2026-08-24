"""Agent loop — the core execution loop with tool calling.

Implements the LLM ↔ tool interaction loop: send messages to the
provider, receive tool calls, execute tools, feed results back,
repeat until the model produces a final answer or a budget limit
is reached.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.agents.domain.tool_execution import (
    SafeToolExecutor,
    ToolRegistry,
)
from app.agents.domain.trajectory import (
    ToolCallRecord,
    TrajectoryStatus,
)
from app.agents.runtime.trajectory_recorder import TrajectoryRecorder
from app.providers.contracts.tool_calling import ToolCallingProvider

if TYPE_CHECKING:
    from app.providers.contracts.chat import ChatProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentLoopConfig:
    """Configuration for the agent execution loop."""

    max_steps: int = 10
    max_retries: int = 3
    timeout_seconds: int = 300
    temperature: float = 0.0
    max_tokens: int | None = None
    system_prompt: str = ""


@dataclass(frozen=True, slots=True)
class AgentLoopResult:
    """Result of the agent loop execution."""

    success: bool = True
    final_response: str = ""
    total_steps: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    error: str | None = None
    status: str = "completed"

    @property
    def total_tokens(self) -> int:
        return self.total_tokens_input + self.total_tokens_output


class AgentLoop:
    """Executes the LLM ↔ tool interaction loop.

    The loop sends the conversation to the provider, checks if the
    response contains tool calls, executes them, appends results,
    and repeats. Terminates when:
    - The model produces a response with no tool calls (final answer)
    - max_steps is reached
    - An unrecoverable error occurs
    """

    def __init__(
        self,
        provider: ChatProvider | ToolCallingProvider,
        tool_registry: ToolRegistry,
        config: AgentLoopConfig | None = None,
    ) -> None:
        self._provider = provider
        self._tool_registry = tool_registry
        self._tool_executor = SafeToolExecutor(tool_registry)
        self._config = config or AgentLoopConfig()

    async def execute(
        self,
        user_message: str,
        *,
        recorder: TrajectoryRecorder | None = None,
    ) -> AgentLoopResult:
        """Execute the agent loop with a user message.

        Args:
            user_message: The initial user task/message.
            recorder: Optional trajectory recorder for evaluation.

        Returns:
            AgentLoopResult with the final response and metrics.
        """
        start = time.monotonic()
        messages: list[dict[str, Any]] = []

        if self._config.system_prompt:
            messages.append({
                "role": "system",
                "content": self._config.system_prompt,
            })

        messages.append({"role": "user", "content": user_message})

        tools_schema = self._tool_registry.get_openai_schemas()
        has_tools = len(tools_schema) > 0 and self._provider_supports_tools()

        total_tokens_input = 0
        total_tokens_output = 0
        total_cost = 0.0
        step_count = 0
        llm_call_count = 0
        tool_call_count = 0

        try:
            while step_count < self._config.max_steps:
                step_start = time.monotonic()

                if has_tools and isinstance(
                    self._provider, ToolCallingProvider
                ):
                    response = await self._provider.chat_with_tools(
                        messages=[
                            self._dict_to_message(m) for m in messages
                        ],
                        model="",
                        tools=list(tools_schema),
                    )
                else:
                    from app.providers.contracts.chat import ChatProvider

                    if isinstance(self._provider, ChatProvider):
                        response = await self._provider.chat(
                            messages=[
                                self._dict_to_message(m) for m in messages
                            ],
                            model="",
                        )
                    else:
                        msg = "Provider does not support chat"
                        raise TypeError(msg)

                step_elapsed = int((time.monotonic() - step_start) * 1000)
                llm_call_count += 1
                total_tokens_input += response.usage.input_tokens
                total_tokens_output += response.usage.output_tokens
                total_cost += getattr(response, "cost_usd", 0.0)

                tool_calls_in_response = response.tool_calls
                has_tool_calls = len(tool_calls_in_response) > 0

                if recorder is not None:
                    recorded_tool_calls = tuple(
                        ToolCallRecord(
                            tool_call_id=tc.tool_call_id,
                            tool_name=tc.name,
                            arguments=json.loads(tc.arguments)
                            if tc.arguments
                            else {},
                        )
                        for tc in tool_calls_in_response
                    )
                    recorder.record_llm_call(
                        provider=response.provider,
                        model=response.model,
                        messages_sent=len(messages),
                        response_content=response.content,
                        tool_calls_requested=recorded_tool_calls,
                        tokens_input=response.usage.input_tokens,
                        tokens_output=response.usage.output_tokens,
                        latency_ms=step_elapsed,
                        finish_reason=response.finish_reason.value
                        if hasattr(response.finish_reason, "value")
                        else str(response.finish_reason),
                    )

                if not has_tool_calls:
                    if recorder is not None:
                        recorder.record_final_answer(response.content)

                    elapsed = int((time.monotonic() - start) * 1000)
                    return AgentLoopResult(
                        success=True,
                        final_response=response.content,
                        total_steps=step_count,
                        total_llm_calls=llm_call_count,
                        total_tool_calls=tool_call_count,
                        total_tokens_input=total_tokens_input,
                        total_tokens_output=total_tokens_output,
                        total_cost_usd=total_cost,
                        total_duration_ms=elapsed,
                        status="completed",
                    )

                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": tc.tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": tc.arguments,
                            },
                        }
                        for tc in tool_calls_in_response
                    ],
                })

                for tc in tool_calls_in_response:
                    step_count += 1
                    tool_call_count += 1

                    try:
                        args = json.loads(tc.arguments) if tc.arguments else {}
                    except json.JSONDecodeError:
                        args = {}

                    tool_start = time.monotonic()
                    tool_result = self._tool_executor.execute(tc.name, args)
                    tool_elapsed = int(
                        (time.monotonic() - tool_start) * 1000
                    )

                    if recorder is not None:
                        recorder.record_tool_call(
                            tool_call_id=tc.tool_call_id,
                            tool_name=tc.name,
                            arguments=args,
                            result=tool_result.result,
                            is_error=tool_result.is_error,
                            latency_ms=tool_elapsed,
                        )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.tool_call_id,
                        "content": tool_result.result
                        if tool_result.is_success
                        else f"Error: {tool_result.error}",
                    })

            elapsed = int((time.monotonic() - start) * 1000)
            if recorder is not None:
                recorder.set_status(TrajectoryStatus.MAX_STEPS_REACHED)
            return AgentLoopResult(
                success=False,
                total_steps=step_count,
                total_llm_calls=llm_call_count,
                total_tool_calls=tool_call_count,
                total_tokens_input=total_tokens_input,
                total_tokens_output=total_tokens_output,
                total_cost_usd=total_cost,
                total_duration_ms=elapsed,
                error="Maximum steps reached without final answer",
                status="max_steps_reached",
            )

        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.exception("Agent loop execution failed")
            if recorder is not None:
                recorder.set_error(str(exc))
            return AgentLoopResult(
                success=False,
                total_steps=step_count,
                total_llm_calls=llm_call_count,
                total_tool_calls=tool_call_count,
                total_tokens_input=total_tokens_input,
                total_tokens_output=total_tokens_output,
                total_cost_usd=total_cost,
                total_duration_ms=elapsed,
                error=str(exc),
                status="failed",
            )

    def execute_sync(
        self,
        user_message: str,
        *,
        recorder: TrajectoryRecorder | None = None,
    ) -> AgentLoopResult:
        """Synchronous wrapper for execute()."""
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.execute(user_message, recorder=recorder)
            )
        finally:
            loop.close()

    def _provider_supports_tools(self) -> bool:
        """Check if the provider implements ToolCallingProvider."""
        from app.providers.contracts.tool_calling import ToolCallingProvider

        return isinstance(self._provider, ToolCallingProvider)

    @staticmethod
    def _dict_to_message(data: dict[str, Any]) -> Any:
        """Convert a dict to a provider Message object."""
        from app.providers.models.enums import MessageRole
        from app.providers.models.messages import Message

        role_str = data.get("role", "user")
        role_map = {
            "system": MessageRole.SYSTEM,
            "user": MessageRole.USER,
            "assistant": MessageRole.ASSISTANT,
            "tool": MessageRole.TOOL,
        }
        role = role_map.get(role_str, MessageRole.USER)
        content = data.get("content", "")

        if role == MessageRole.TOOL:
            tool_call_id = data.get("tool_call_id", "")
            return Message.tool(
                tool_call_id=tool_call_id,
                content=content,
            )

        return Message(role=role, content=content)
