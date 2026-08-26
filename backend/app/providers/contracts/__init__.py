"""Provider contracts.

Defines the interfaces that all providers must implement.
Contracts are organized by capability domain to ensure
providers only expose relevant methods.
"""

from __future__ import annotations

from app.providers.contracts.base import BaseProvider
from app.providers.contracts.chat import ChatProvider
from app.providers.contracts.embedding import EmbeddingProvider
from app.providers.contracts.reasoning import ReasoningProvider
from app.providers.contracts.streaming import StreamingProvider
from app.providers.contracts.tool_calling import ToolCallingProvider

__all__ = [
    "BaseProvider",
    "ChatProvider",
    "EmbeddingProvider",
    "ReasoningProvider",
    "StreamingProvider",
    "ToolCallingProvider",
]
