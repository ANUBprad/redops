"""Message types for provider interactions.

Provider-agnostic message representations covering text, images,
audio, tool calls, and tool results. All messages are immutable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.models.enums import MessageRole


@dataclass(frozen=True, slots=True)
class TextContent:
    """A text content block."""

    text: str


@dataclass(frozen=True, slots=True)
class ImageContent:
    """An image content block (URL or base64)."""

    url: str | None = None
    base64_data: str | None = None
    media_type: str = "image/png"
    detail: str = "auto"


@dataclass(frozen=True, slots=True)
class AudioContent:
    """An audio content block."""

    data: str
    media_type: str = "audio/wav"


@dataclass(frozen=True, slots=True)
class ToolCallContent:
    """A tool call initiated by the model."""

    tool_call_id: str
    name: str
    arguments: str = ""


@dataclass(frozen=True, slots=True)
class ToolResultContent:
    """A result returned by a tool invocation."""

    tool_call_id: str
    content: str
    is_error: bool = False


ContentBlock = TextContent | ImageContent | AudioContent | ToolCallContent | ToolResultContent


@dataclass(frozen=True, slots=True)
class Message:
    """A single message in a conversation.

    Messages carry a role and one or more content blocks.
    Content is represented as a sequence of typed blocks
    to support multimodal inputs.
    """

    role: MessageRole
    content: str | list[ContentBlock] = ""

    @classmethod
    def system(cls, text: str) -> Message:
        """Create a system message."""
        return cls(role=MessageRole.SYSTEM, content=text)

    @classmethod
    def user(cls, text: str) -> Message:
        """Create a user message with text content."""
        return cls(role=MessageRole.USER, content=text)

    @classmethod
    def assistant(cls, text: str) -> Message:
        """Create an assistant message with text content."""
        return cls(role=MessageRole.ASSISTANT, content=text)

    @classmethod
    def tool(cls, tool_call_id: str, content: str, *, is_error: bool = False) -> Message:
        """Create a tool result message."""
        block = ToolResultContent(
            tool_call_id=tool_call_id,
            content=content,
            is_error=is_error,
        )
        return cls(role=MessageRole.TOOL, content=[block])
