"""Provider domain enums.

Standard enumerations for message roles, finish reasons,
modalities, and model status. Provider-agnostic.
"""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class MessageRole(StrEnum):
    """Role of a message in a conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@unique
class FinishReason(StrEnum):
    """Reason the model stopped generating."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    MAX_TOKENS = "max_tokens"
    UNKNOWN = "unknown"


@unique
class Modality(StrEnum):
    """Supported input/output modalities."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"


@unique
class ModelStatus(StrEnum):
    """Lifecycle status of a model."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"
    BETA = "beta"
    PRIVATE_PREVIEW = "private_preview"
