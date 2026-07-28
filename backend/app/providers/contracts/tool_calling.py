"""Tool calling provider contract.

Defines the interface for providers that support function
calling and tool invocation.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.providers.models.messages import Message
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse


class ToolCallingProvider:
    """Interface for tool-calling-capable providers.

    Providers that support function calling must implement
    this interface. Tool definitions are passed as part of
    ChatOptions, and tool results are passed as ToolResultContent
    in messages.
    """

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None = None,
        options: ChatOptions | None = None,
    ) -> ChatResponse:
        """Generate a chat completion with tool calling.

        The model may respond with tool calls that should
        be executed by the caller, then fed back as
        ToolResultContent messages.

        Args:
            messages: The conversation messages.
            model: The model identifier to use.
            tools: Tool definitions in OpenAI-compatible format.
            tool_choice: Tool selection strategy.
            options: Optional generation parameters.

        Returns:
            Response potentially containing tool calls.

        Raises:
            InvalidModel: If the model does not support tools.
            ProviderUnavailable: If the provider is down.

        """
