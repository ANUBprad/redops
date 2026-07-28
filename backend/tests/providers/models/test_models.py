"""Tests for model types."""

from __future__ import annotations

import pytest

from app.providers.models.enums import FinishReason, MessageRole, Modality, ModelStatus
from app.providers.models.messages import (
    AudioContent,
    ImageContent,
    Message,
    TextContent,
    ToolCallContent,
    ToolResultContent,
)
from app.providers.models.options import ChatOptions, EmbeddingOptions, ProviderRequestOptions
from app.providers.models.responses import ChatResponse, EmbeddingResponse, Usage


class TestEnums:
    """Tests for enum types."""

    def test_message_role_values(self) -> None:
        assert MessageRole.SYSTEM == "system"
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.TOOL == "tool"

    def test_finish_reason_values(self) -> None:
        assert FinishReason.STOP == "stop"
        assert FinishReason.LENGTH == "length"
        assert FinishReason.TOOL_CALLS == "tool_calls"

    def test_modality_values(self) -> None:
        assert Modality.TEXT == "text"
        assert Modality.IMAGE == "image"
        assert Modality.AUDIO == "audio"

    def test_model_status_values(self) -> None:
        assert ModelStatus.ACTIVE == "active"
        assert ModelStatus.DEPRECATED == "deprecated"
        assert ModelStatus.RETIRED == "retired"


class TestMessages:
    """Tests for message types."""

    def test_text_content(self) -> None:
        tc = TextContent(text="hello")
        assert tc.text == "hello"

    def test_image_content_url(self) -> None:
        ic = ImageContent(url="https://example.com/img.png")
        assert ic.url == "https://example.com/img.png"
        assert ic.media_type == "image/png"

    def test_image_content_base64(self) -> None:
        ic = ImageContent(base64_data="abc123")
        assert ic.base64_data == "abc123"

    def test_audio_content(self) -> None:
        ac = AudioContent(data="audio_base64")
        assert ac.data == "audio_base64"

    def test_tool_call_content(self) -> None:
        tc = ToolCallContent(tool_call_id="tc_1", name="get_weather", arguments='{"city":"NYC"}')
        assert tc.tool_call_id == "tc_1"
        assert tc.name == "get_weather"

    def test_tool_result_content(self) -> None:
        tr = ToolResultContent(tool_call_id="tc_1", content="72F")
        assert tr.tool_call_id == "tc_1"
        assert tr.is_error is False

    def test_tool_result_error(self) -> None:
        tr = ToolResultContent(tool_call_id="tc_1", content="error", is_error=True)
        assert tr.is_error is True

    def test_message_system(self) -> None:
        m = Message.system("You are helpful")
        assert m.role == MessageRole.SYSTEM
        assert m.content == "You are helpful"

    def test_message_user(self) -> None:
        m = Message.user("Hello")
        assert m.role == MessageRole.USER
        assert m.content == "Hello"

    def test_message_assistant(self) -> None:
        m = Message.assistant("Hi there")
        assert m.role == MessageRole.ASSISTANT

    def test_message_tool(self) -> None:
        m = Message.tool("tc_1", "result")
        assert m.role == MessageRole.TOOL
        assert isinstance(m.content, list)
        assert len(m.content) == 1

    def test_message_frozen(self) -> None:
        m = Message.user("test")
        with pytest.raises(AttributeError):
            m.content = "changed"  # type: ignore[misc]


class TestOptions:
    """Tests for request options."""

    def test_provider_request_options_defaults(self) -> None:
        opts = ProviderRequestOptions()
        assert opts.temperature is None
        assert opts.max_tokens is None

    def test_chat_options(self) -> None:
        opts = ChatOptions(
            temperature=0.7,
            max_tokens=1000,
            system_prompt="Be helpful",
        )
        assert opts.temperature == 0.7
        assert opts.system_prompt == "Be helpful"

    def test_embedding_options(self) -> None:
        opts = EmbeddingOptions(dimensions=1536)
        assert opts.dimensions == 1536
        assert opts.encoding_format == "float"


class TestResponses:
    """Tests for response types."""

    def test_usage_auto_total(self) -> None:
        u = Usage(input_tokens=100, output_tokens=50)
        assert u.total_tokens == 150

    def test_usage_explicit_total(self) -> None:
        u = Usage(input_tokens=100, output_tokens=50, total_tokens=200)
        assert u.total_tokens == 200

    def test_chat_response(self) -> None:
        r = ChatResponse(
            model="test-model",
            provider="test",
            usage=Usage(input_tokens=10, output_tokens=5),
            content="Hello",
        )
        assert r.content == "Hello"
        assert r.model == "test-model"

    def test_embedding_response(self) -> None:
        r = EmbeddingResponse(
            model="test-model",
            provider="test",
            usage=Usage(input_tokens=10, output_tokens=0),
            embedding=(0.1, 0.2, 0.3),
            dimensions=3,
        )
        assert len(r.embedding) == 3
        assert r.dimensions == 3
