"""Tests for tool calling adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.models.messages import Message
from app.providers.openai.adapters.contracts import OpenAIToolCallingAdapter


class TestOpenAIToolCallingAdapter:
    """Tests for OpenAIToolCallingAdapter."""

    @pytest.mark.asyncio
    async def test_chat_with_tools(self) -> None:
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.model = "gpt-4o"
        mock_response.id = "chatcmpl-123"
        mock_response.system_fingerprint = None
        usage = MagicMock()
        usage.prompt_tokens = 10
        usage.completion_tokens = 5
        usage.total_tokens = 15
        usage.prompt_tokens_details = None
        usage.completion_tokens_details = None
        mock_response.usage = usage

        tc = MagicMock()
        tc.id = "call_abc"
        func = MagicMock()
        func.name = "get_weather"
        func.arguments = '{"city":"NYC"}'
        tc.function = func

        choice = MagicMock()
        choice.finish_reason = "tool_calls"
        message = MagicMock()
        message.content = None
        message.tool_calls = [tc]
        choice.message = message
        mock_response.choices = [choice]

        client.create_chat_completion = AsyncMock(return_value=mock_response)

        adapter = OpenAIToolCallingAdapter(client)
        tools = [{"type": "function", "function": {"name": "get_weather"}}]
        messages = [Message.user("What's the weather?")]

        result = await adapter.chat_with_tools(
            messages,
            model="gpt-4o",
            tools=tools,
            tool_choice="auto",
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_weather"
        client.create_chat_completion.assert_called_once()
