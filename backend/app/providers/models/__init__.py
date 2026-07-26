"""Provider domain models.

Base types for messages, responses, options, and enums used
throughout the Provider Framework. These are provider-agnostic
data structures that all providers must produce and consume.
"""

from __future__ import annotations

from app.providers.models.enums import (
    FinishReason,
    MessageRole,
    Modality,
    ModelStatus,
)
from app.providers.models.messages import (
    AudioContent,
    ContentBlock,
    ImageContent,
    Message,
    TextContent,
    ToolCallContent,
    ToolResultContent,
)
from app.providers.models.options import (
    ChatOptions,
    EmbeddingOptions,
    ProviderRequestOptions,
)
from app.providers.models.responses import (
    ChatResponse,
    EmbeddingResponse,
    ProviderResponse,
    Usage,
)

__all__ = [
    "AudioContent",
    "ChatOptions",
    "ChatResponse",
    "ContentBlock",
    "EmbeddingOptions",
    "EmbeddingResponse",
    "FinishReason",
    "ImageContent",
    "Message",
    "MessageRole",
    "Modality",
    "ModelStatus",
    "ProviderRequestOptions",
    "ProviderResponse",
    "TextContent",
    "ToolCallContent",
    "ToolResultContent",
    "Usage",
]
