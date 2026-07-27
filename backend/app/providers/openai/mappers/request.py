"""OpenAI request mapping — converts framework models to OpenAI payloads."""

from __future__ import annotations

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
) -> list[dict[str, Any]]:
    """Map framework messages to OpenAI message format.

    Args:
        messages: Framework message objects.
        system_prompt: Optional system prompt to inject.

    Returns:
        List of OpenAI-compatible message dicts.

    """
    result: list[dict[str, Any]] = []

    if system_prompt:
        result.append({"role": "system", "content": system_prompt})

    for msg in messages:
        mapped = _map_single_message(msg)
        if mapped is not None:
            result.append(mapped)

    return result


def _map_single_message(message: Message) -> dict[str, Any] | None:
    """Map a single framework message to OpenAI format."""
    role = message.role

    if isinstance(message.content, str):
        return _map_text_content(role, message.content)

    if isinstance(message.content, list):
        return _map_content_blocks(role, message.content)

    return None


def _map_text_content(role: MessageRole, content: str) -> dict[str, Any]:
    """Map a text-only message."""
    return {"role": role.value, "content": content}


def _map_content_blocks(
    role: MessageRole,
    blocks: list[Any],
) -> dict[str, Any]:
    """Map a message with typed content blocks."""
    if not blocks:
        return {"role": role.value, "content": ""}

    if len(blocks) == 1:
        return _map_single_block(role, blocks[0])

    return _map_mixed_blocks(role, blocks)


def _map_single_block(role: MessageRole, block: Any) -> dict[str, Any]:  # noqa: ANN401
    """Map a single content block."""
    if isinstance(block, TextContent):
        return {"role": role.value, "content": block.text}
    if isinstance(block, ToolResultContent):
        return _map_tool_result(block)
    if isinstance(block, ToolCallContent):
        return _map_tool_call_content(block)
    return _map_mixed_blocks(role, [block])


def _map_mixed_blocks(
    role: MessageRole,
    blocks: list[Any],
) -> dict[str, Any]:
    """Map multiple mixed content blocks."""
    parts: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []

    for block in blocks:
        if isinstance(block, TextContent):
            parts.append({"type": "text", "text": block.text})
        elif isinstance(block, ImageContent):
            parts.append(_map_image_content(block))
        elif isinstance(block, AudioContent):
            parts.append(_map_audio_content(block))
        elif isinstance(block, ToolCallContent):
            tool_calls.append(_map_tool_call_to_dict(block))
        elif isinstance(block, ToolResultContent):
            return _map_tool_result(block)

    if tool_calls:
        return {
            "role": role.value,
            "content": None,
            "tool_calls": tool_calls,
        }

    if len(parts) == 1:
        return {"role": role.value, "content": parts[0]}

    return {"role": role.value, "content": parts}


def _map_image_content(block: ImageContent) -> dict[str, Any]:
    """Map an image content block to OpenAI format."""
    if block.url:
        return {
            "type": "image_url",
            "image_url": {
                "url": block.url,
                "detail": block.detail,
            },
        }

    if block.base64_data:
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{block.media_type};base64,{block.base64_data}",
                "detail": block.detail,
            },
        }

    return {"type": "text", "text": "[image content missing data]"}


def _map_audio_content(block: AudioContent) -> dict[str, Any]:
    """Map an audio content block to OpenAI format."""
    return {
        "type": "input_audio",
        "input_audio": {
            "data": block.data,
            "format": block.media_type.split("/")[-1],
        },
    }


def _map_tool_result(block: ToolResultContent) -> dict[str, Any]:
    """Map a tool result to OpenAI format."""
    return {
        "role": "tool",
        "tool_call_id": block.tool_call_id,
        "content": block.content,
    }


def _map_tool_call_content(block: ToolCallContent) -> dict[str, Any]:
    """Map a ToolCallContent to assistant message with tool_calls."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [_map_tool_call_to_dict(block)],
    }


def _map_tool_call_to_dict(block: ToolCallContent) -> dict[str, Any]:
    """Map a ToolCallContent to an OpenAI tool_call dict."""
    return {
        "id": block.tool_call_id,
        "type": "function",
        "function": {
            "name": block.name,
            "arguments": block.arguments,
        },
    }


def map_chat_options(options: ChatOptions | None) -> dict[str, Any]:
    """Map framework ChatOptions to OpenAI API parameters.

    Args:
        options: Framework chat options.

    Returns:
        Dict of OpenAI-compatible API parameters.

    """
    if options is None:
        return {}

    params: dict[str, Any] = {}
    _apply_sampling_params(options, params)
    _apply_constraint_params(options, params)
    _apply_output_params(options, params)
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
    if options.seed is not None:
        params["seed"] = options.seed


def _apply_constraint_params(
    options: ChatOptions,
    params: dict[str, Any],
) -> None:
    """Apply constraint parameters."""
    if options.max_tokens is not None:
        params["max_tokens"] = options.max_tokens
    if options.stop is not None:
        params["stop"] = options.stop
    if options.presence_penalty is not None:
        params["presence_penalty"] = options.presence_penalty
    if options.frequency_penalty is not None:
        params["frequency_penalty"] = options.frequency_penalty


def _apply_output_params(
    options: ChatOptions,
    params: dict[str, Any],
) -> None:
    """Apply output format parameters."""
    if options.logprobs is not None:
        params["logprobs"] = options.logprobs
    if options.top_logprobs is not None:
        params["top_logprobs"] = options.top_logprobs
    if options.response_format is not None:
        params["response_format"] = options.response_format
    if options.parallel_tool_calls is not None:
        params["parallel_tool_calls"] = options.parallel_tool_calls


def map_tools(
    tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure tools are in OpenAI function-calling format.

    Args:
        tools: Tool definitions (already OpenAI-compatible).

    Returns:
        The tools in OpenAI format.

    """
    return tools
