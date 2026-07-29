"""Anthropic request mapping — converts framework models to Anthropic payloads."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from app.providers.models.messages import (
    AudioContent,
    ImageContent,
    Message,
    TextContent,
    ToolCallContent,
    ToolResultContent,
)

if TYPE_CHECKING:
    from app.providers.models.enums import MessageRole
    from app.providers.models.options import ChatOptions


def map_messages(
    messages: list[Message],
    *,
    system_prompt: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Map framework messages to Anthropic message format.

    Args:
        messages: Framework message objects.
        system_prompt: Optional system prompt to inject.

    Returns:
        Tuple of (messages list, system prompt or None).

    """
    result: list[dict[str, Any]] = []
    system = system_prompt

    for msg in messages:
        mapped = _map_single_message(msg)
        if mapped is not None:
            result.append(mapped)

    return result, system


def _map_single_message(message: Message) -> dict[str, Any] | None:
    """Map a single framework message to Anthropic format."""
    role = message.role

    if isinstance(message.content, str):
        return _map_text_content(role, message.content)

    if isinstance(message.content, list):
        return _map_content_blocks(role, message.content)

    return None


def _map_text_content(role: MessageRole, content: str) -> dict[str, Any]:
    """Map a text-only message."""
    anthropic_role = _map_role(role)
    if anthropic_role is None:
        return {"role": "user", "content": content}
    return {"role": anthropic_role, "content": content}


def _map_role(role: MessageRole) -> str | None:
    """Map framework role to Anthropic role. None if needs special handling."""
    if role.value == "system":
        return None
    if role.value == "tool":
        return None
    return role.value


def _map_content_blocks(
    role: MessageRole,
    blocks: list[Any],
) -> dict[str, Any]:
    """Map a message with typed content blocks."""
    if not blocks:
        anthropic_role = _map_role(role) or "user"
        return {"role": anthropic_role, "content": ""}

    if role.value == "tool":
        return _map_tool_result_blocks(blocks)

    if role.value == "assistant":
        return _map_assistant_blocks(blocks)

    anthropic_role = _map_role(role) or "user"
    return _map_user_blocks(anthropic_role, blocks)


def _map_tool_result_blocks(blocks: list[Any]) -> dict[str, Any]:
    """Map tool result blocks to Anthropic user message with tool_result content."""
    content: list[dict[str, Any]] = [
        {
            "type": "tool_result",
            "tool_use_id": block.tool_call_id,
            "content": block.content,
        }
        for block in blocks
        if isinstance(block, ToolResultContent)
    ]
    return {"role": "user", "content": content}


def _map_assistant_blocks(blocks: list[Any]) -> dict[str, Any]:
    """Map assistant message content blocks to Anthropic format."""
    content: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, TextContent):
            content.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolCallContent):
            content.append(_map_tool_call_block(block))
    return {"role": "assistant", "content": content}


def _map_tool_call_block(block: ToolCallContent) -> dict[str, Any]:
    """Map a ToolCallContent to Anthropic tool_use block."""
    return {
        "type": "tool_use",
        "id": block.tool_call_id,
        "name": block.name,
        "input": _parse_tool_arguments(block.arguments),
    }


def _parse_tool_arguments(arguments: str) -> dict[str, Any]:
    """Parse tool arguments from JSON string to dict."""
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
    except (json.JSONDecodeError, TypeError):
        return {}
    else:
        return parsed if isinstance(parsed, dict) else {}


def _map_user_blocks(
    role: str,
    blocks: list[Any],
) -> dict[str, Any]:
    """Map user message content blocks to Anthropic format."""
    content: list[dict[str, Any]] = []
    for block in blocks:
        if isinstance(block, TextContent):
            content.append({"type": "text", "text": block.text})
        elif isinstance(block, ImageContent):
            content.append(_map_image_content(block))
        elif isinstance(block, AudioContent):
            content.append(_map_audio_content(block))
    if len(content) == 1:
        return {"role": role, "content": content[0]}
    return {"role": role, "content": content}


def _map_image_content(block: ImageContent) -> dict[str, Any]:
    """Map an image content block to Anthropic format."""
    if block.url:
        return {
            "type": "image",
            "source": {
                "type": "url",
                "url": block.url,
            },
        }

    if block.base64_data:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": block.media_type,
                "data": block.base64_data,
            },
        }

    return {"type": "text", "text": "[image content missing data]"}


def _map_audio_content(block: AudioContent) -> dict[str, Any]:
    """Map an audio content block to Anthropic format."""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": block.media_type,
            "data": block.data,
        },
    }


def map_chat_options(options: ChatOptions | None) -> dict[str, Any]:
    """Map framework ChatOptions to Anthropic API parameters."""
    if options is None:
        return {}

    params: dict[str, Any] = {}
    _apply_sampling_params(options, params)
    _apply_constraint_params(options, params)
    return params


def _apply_sampling_params(
    options: ChatOptions,
    params: dict[str, Any],
) -> None:
    """Apply sampling-related parameters."""
    if options.temperature is not None:
        params["temperature"] = options.temperature
    if options.top_p is not None:
        params["top_p"] = options.top_p


def _apply_constraint_params(
    options: ChatOptions,
    params: dict[str, Any],
) -> None:
    """Apply constraint parameters."""
    if options.max_tokens is not None:
        params["max_tokens"] = options.max_tokens
    if options.stop is not None:
        params["stop_sequences"] = options.stop


def map_tools(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI-format tools to Anthropic tool format.

    Args:
        tools: Tool definitions in OpenAI function-calling format.

    Returns:
        Tools in Anthropic format with input_schema.

    """
    result: list[dict[str, Any]] = []
    for tool in tools:
        func = tool.get("function", {})
        result.append(
            {
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            }
        )
    return result


def map_tool_choice(
    tool_choice: str | dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Convert OpenAI tool_choice to Anthropic format.

    Args:
        tool_choice: OpenAI tool_choice value.

    Returns:
        Anthropic tool_choice dict or None.

    """
    if tool_choice is None:
        return None
    if tool_choice == "auto":
        return {"type": "auto"}
    if tool_choice == "required":
        return {"type": "any"}
    if isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
        return {"type": "tool", "name": tool_choice.get("function", {}).get("name", "")}
    if isinstance(tool_choice, dict):
        return tool_choice
    return {"type": "auto"}
