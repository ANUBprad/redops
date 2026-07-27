"""Tests for OpenAI request mapping."""

from app.providers.models.enums import MessageRole
from app.providers.models.messages import (
    ImageContent,
    Message,
    TextContent,
    ToolCallContent,
    ToolResultContent,
)
from app.providers.models.options import ChatOptions
from app.providers.openai.mappers.request import map_chat_options, map_messages


class TestMapMessages:
    """Tests for map_messages."""

    def test_simple_text_messages(self) -> None:
        messages = [
            Message.system("You are helpful"),
            Message.user("Hello"),
            Message.assistant("Hi there"),
        ]
        result = map_messages(messages)
        assert len(result) == 3
        assert result[0] == {"role": "system", "content": "You are helpful"}
        assert result[1] == {"role": "user", "content": "Hello"}
        assert result[2] == {"role": "assistant", "content": "Hi there"}

    def test_system_prompt_injection(self) -> None:
        messages = [Message.user("Hi")]
        result = map_messages(messages, system_prompt="Be helpful")
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "Be helpful"
        assert result[1]["role"] == "user"

    def test_no_system_prompt_when_none(self) -> None:
        messages = [Message.user("Hi")]
        result = map_messages(messages, system_prompt=None)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_tool_result_message(self) -> None:
        msg = Message.tool(tool_call_id="call_123", content='{"temp": 72}')
        result = map_messages([msg])
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "call_123"
        assert result[0]["content"] == '{"temp": 72}'

    def test_multimodal_text_and_image(self) -> None:
        blocks = [
            TextContent(text="What is this?"),
            ImageContent(url="https://example.com/img.png"),
        ]
        msg = Message(role=MessageRole.USER, content=blocks)
        result = map_messages([msg])
        assert result[0]["role"] == "user"
        content = result[0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"] == "https://example.com/img.png"

    def test_image_base64(self) -> None:
        blocks = [ImageContent(base64_data="abc123", media_type="image/jpeg")]
        msg = Message(role=MessageRole.USER, content=blocks)
        result = map_messages([msg])
        content = result[0]["content"]
        assert isinstance(content, dict)
        url = content["image_url"]["url"]
        assert url.startswith("data:image/jpeg;base64,")

    def test_tool_call_content(self) -> None:
        blocks = [
            ToolCallContent(tool_call_id="call_1", name="get_weather", arguments='{"city":"NYC"}'),
        ]
        msg = Message(role=MessageRole.ASSISTANT, content=blocks)
        result = map_messages([msg])
        assert result[0]["role"] == "assistant"
        assert result[0]["tool_calls"][0]["id"] == "call_1"
        assert result[0]["tool_calls"][0]["function"]["name"] == "get_weather"


class TestMapChatOptions:
    """Tests for map_chat_options."""

    def test_none_options(self) -> None:
        assert map_chat_options(None) == {}

    def test_all_options(self) -> None:
        options = ChatOptions(
            temperature=0.7,
            top_p=0.9,
            max_tokens=1000,
            stop=["END"],
            seed=42,
            presence_penalty=0.5,
            frequency_penalty=0.3,
            logprobs=True,
            top_logprobs=5,
            parallel_tool_calls=False,
        )
        result = map_chat_options(options)
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9
        assert result["max_tokens"] == 1000
        assert result["stop"] == ["END"]
        assert result["seed"] == 42
        assert result["presence_penalty"] == 0.5
        assert result["frequency_penalty"] == 0.3
        assert result["logprobs"] is True
        assert result["top_logprobs"] == 5
        assert result["parallel_tool_calls"] is False

    def test_none_values_excluded(self) -> None:
        options = ChatOptions(temperature=0.5)
        result = map_chat_options(options)
        assert "top_p" not in result
        assert "max_tokens" not in result
        assert result["temperature"] == 0.5

    def test_response_format(self) -> None:
        options = ChatOptions(
            response_format={"type": "json_object"},
        )
        result = map_chat_options(options)
        assert result["response_format"] == {"type": "json_object"}
