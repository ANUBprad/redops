"""Tests for Anthropic request mapping."""

import json

from app.providers.models.enums import MessageRole
from app.providers.models.messages import (
    AudioContent,
    ImageContent,
    Message,
    TextContent,
    ToolCallContent,
    ToolResultContent,
)
from app.providers.models.options import ChatOptions
from app.providers.anthropic.mappers.request import (
    map_chat_options,
    map_messages,
    map_tool_choice,
    map_tools,
)


class TestMapMessages:
    """Tests for map_messages."""

    def test_simple_text_messages(self) -> None:
        messages = [
            Message.user("Hello"),
            Message.assistant("Hi there"),
        ]
        result, system = map_messages(messages)
        assert system is None
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there"}

    def test_system_prompt_extracted_separately(self) -> None:
        messages = [Message.user("Hi")]
        result, system = map_messages(messages, system_prompt="Be helpful")
        assert system == "Be helpful"
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_no_system_prompt_when_none(self) -> None:
        messages = [Message.user("Hi")]
        result, system = map_messages(messages, system_prompt=None)
        assert system is None
        assert len(result) == 1

    def test_system_message_mapped_to_user(self) -> None:
        messages = [
            Message.system("You are helpful"),
            Message.user("Hello"),
        ]
        result, system = map_messages(messages)
        assert system is None
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "You are helpful"
        assert result[1]["role"] == "user"

    def test_tool_result_message(self) -> None:
        msg = Message.tool(tool_call_id="toolu_123", content='{"temp": 72}')
        result, _ = map_messages([msg])
        assert len(result) == 1
        assert result[0]["role"] == "user"
        content = result[0]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "toolu_123"
        assert content[0]["content"] == '{"temp": 72}'

    def test_multiple_tool_results(self) -> None:
        msg = Message(
            role=MessageRole.TOOL,
            content=[
                ToolResultContent(tool_call_id="toolu_1", content="result1"),
                ToolResultContent(tool_call_id="toolu_2", content="result2"),
            ],
        )
        result, _ = map_messages([msg])
        assert len(result) == 1
        content = result[0]["content"]
        assert len(content) == 2
        assert content[0]["tool_use_id"] == "toolu_1"
        assert content[1]["tool_use_id"] == "toolu_2"

    def test_assistant_text_only(self) -> None:
        msg = Message.assistant("Hello!")
        result, _ = map_messages([msg])
        assert result[0] == {"role": "assistant", "content": "Hello!"}

    def test_assistant_with_tool_call(self) -> None:
        blocks = [
            TextContent(text="Let me check that."),
            ToolCallContent(
                tool_call_id="toolu_abc",
                name="get_weather",
                arguments=json.dumps({"city": "NYC"}),
            ),
        ]
        msg = Message(role=MessageRole.ASSISTANT, content=blocks)
        result, _ = map_messages([msg])
        assert result[0]["role"] == "assistant"
        content = result[0]["content"]
        assert len(content) == 2
        assert content[0] == {"type": "text", "text": "Let me check that."}
        assert content[1]["type"] == "tool_use"
        assert content[1]["id"] == "toolu_abc"
        assert content[1]["name"] == "get_weather"
        assert content[1]["input"] == {"city": "NYC"}

    def test_assistant_tool_call_empty_arguments(self) -> None:
        blocks = [
            ToolCallContent(tool_call_id="toolu_1", name="do_something", arguments=""),
        ]
        msg = Message(role=MessageRole.ASSISTANT, content=blocks)
        result, _ = map_messages([msg])
        content = result[0]["content"]
        assert content[0]["input"] == {}

    def test_assistant_tool_call_invalid_json(self) -> None:
        blocks = [
            ToolCallContent(tool_call_id="toolu_1", name="do_something", arguments="not json"),
        ]
        msg = Message(role=MessageRole.ASSISTANT, content=blocks)
        result, _ = map_messages([msg])
        content = result[0]["content"]
        assert content[0]["input"] == {}

    def test_multimodal_text_and_image_url(self) -> None:
        blocks = [
            TextContent(text="What is this?"),
            ImageContent(url="https://example.com/img.png"),
        ]
        msg = Message(role=MessageRole.USER, content=blocks)
        result, _ = map_messages([msg])
        content = result[0]["content"]
        assert isinstance(content, list)
        assert len(content) == 2
        assert content[0] == {"type": "text", "text": "What is this?"}
        assert content[1]["type"] == "image"
        assert content[1]["source"]["type"] == "url"
        assert content[1]["source"]["url"] == "https://example.com/img.png"

    def test_image_base64(self) -> None:
        blocks = [ImageContent(base64_data="abc123", media_type="image/jpeg")]
        msg = Message(role=MessageRole.USER, content=blocks)
        result, _ = map_messages([msg])
        content = result[0]["content"]
        assert content["type"] == "image"
        assert content["source"]["type"] == "base64"
        assert content["source"]["media_type"] == "image/jpeg"
        assert content["source"]["data"] == "abc123"

    def test_image_missing_data(self) -> None:
        blocks = [ImageContent()]
        msg = Message(role=MessageRole.USER, content=blocks)
        result, _ = map_messages([msg])
        content = result[0]["content"]
        assert content["type"] == "text"
        assert "missing data" in content["text"]

    def test_audio_content(self) -> None:
        blocks = [AudioContent(data="audio_base64", media_type="audio/wav")]
        msg = Message(role=MessageRole.USER, content=blocks)
        result, _ = map_messages([msg])
        content = result[0]["content"]
        assert content["type"] == "image"
        assert content["source"]["type"] == "base64"
        assert content["source"]["media_type"] == "audio/wav"

    def test_single_text_block_unwrapped(self) -> None:
        blocks = [TextContent(text="Hello")]
        msg = Message(role=MessageRole.USER, content=blocks)
        result, _ = map_messages([msg])
        content = result[0]["content"]
        assert isinstance(content, dict)
        assert content == {"type": "text", "text": "Hello"}

    def test_empty_content_blocks(self) -> None:
        msg = Message(role=MessageRole.USER, content=[])
        result, _ = map_messages([msg])
        assert result[0]["content"] == ""

    def test_empty_tool_result_blocks(self) -> None:
        msg = Message(role=MessageRole.TOOL, content=[])
        result, _ = map_messages([msg])
        assert result[0]["role"] == "user"
        assert result[0]["content"] == ""


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
        )
        result = map_chat_options(options)
        assert result["temperature"] == 0.7
        assert result["top_p"] == 0.9
        assert result["max_tokens"] == 1000
        assert result["stop_sequences"] == ["END"]

    def test_none_values_excluded(self) -> None:
        options = ChatOptions(temperature=0.5)
        result = map_chat_options(options)
        assert "top_p" not in result
        assert "max_tokens" not in result
        assert "stop_sequences" not in result
        assert result["temperature"] == 0.5


class TestMapTools:
    """Tests for map_tools."""

    def test_empty_tools(self) -> None:
        assert map_tools([]) == []

    def test_single_tool(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather info",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
                },
            }
        ]
        result = map_tools(tools)
        assert len(result) == 1
        assert result[0]["name"] == "get_weather"
        assert result[0]["description"] == "Get weather info"
        assert result[0]["input_schema"]["properties"]["city"]["type"] == "string"

    def test_tool_without_parameters(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "Does nothing",
                },
            }
        ]
        result = map_tools(tools)
        assert result[0]["input_schema"] == {"type": "object", "properties": {}}

    def test_tool_without_function_key(self) -> None:
        tools = [{"type": "function"}]
        result = map_tools(tools)
        assert result[0]["name"] == ""
        assert result[0]["description"] == ""


class TestMapToolChoice:
    """Tests for map_tool_choice."""

    def test_none(self) -> None:
        assert map_tool_choice(None) is None

    def test_auto(self) -> None:
        assert map_tool_choice("auto") == {"type": "auto"}

    def test_required(self) -> None:
        assert map_tool_choice("required") == {"type": "any"}

    def test_function_specific(self) -> None:
        tool_choice = {
            "type": "function",
            "function": {"name": "get_weather"},
        }
        result = map_tool_choice(tool_choice)
        assert result == {"type": "tool", "name": "get_weather"}

    def test_unknown_string(self) -> None:
        result = map_tool_choice("none")
        assert result == {"type": "auto"}

    def test_dict_passthrough(self) -> None:
        custom = {"type": "any"}
        result = map_tool_choice(custom)
        assert result == {"type": "any"}
