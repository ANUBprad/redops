"""Shared fixtures for Anthropic provider tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.models.messages import (
    Message,
)
from app.providers.models.options import ChatOptions


@pytest.fixture
def mock_anthropic_client():
    """Create a mocked AnthropicClient."""
    client = MagicMock()
    client.api_key = "sk-ant...test"
    client.create_message = AsyncMock()
    client.create_message_stream = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def sample_messages():
    """Return a list of sample framework messages."""
    return [
        Message.system("You are helpful"),
        Message.user("Hello"),
        Message.assistant("Hi there"),
    ]


@pytest.fixture
def sample_chat_options():
    """Return sample ChatOptions."""
    return ChatOptions(
        temperature=0.7,
        top_p=0.9,
        max_tokens=1024,
        stop=["END"],
        system_prompt="Be helpful",
    )


@pytest.fixture
def sample_raw_response():
    """Create a mock Anthropic Message response."""
    response = MagicMock()
    response.model = "claude-sonnet-4-20250514"
    response.id = "msg_abc123"
    response.stop_reason = "end_turn"
    response.stop_sequence = None

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hello!"
    response.content = [text_block]

    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    usage.cache_creation_input_tokens = 0
    usage.cache_read_input_tokens = 0
    response.usage = usage

    return response


@pytest.fixture
def sample_tool_response():
    """Create a mock Anthropic Message with tool calls."""
    response = MagicMock()
    response.model = "claude-sonnet-4-20250514"
    response.id = "msg_tool123"
    response.stop_reason = "tool_use"
    response.stop_sequence = None

    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_abc"
    tool_block.name = "get_weather"
    tool_block.input = {"city": "NYC"}
    response.content = [tool_block]

    usage = MagicMock()
    usage.input_tokens = 20
    usage.output_tokens = 15
    usage.cache_creation_input_tokens = 0
    usage.cache_read_input_tokens = 0
    response.usage = usage

    return response
