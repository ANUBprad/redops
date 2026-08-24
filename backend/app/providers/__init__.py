"""Provider Framework for RedOps Eval.

Provides the abstraction layer that allows the Evaluation Engine
to interact with any AI provider through identical interfaces.
No concrete provider implementations exist in this package.

Usage:
    from app.providers import ProviderRegistry, ModelCatalog
    from app.providers.contracts import ChatProvider
    from app.providers.capabilities import Capability

    # Register providers
    registry = ProviderRegistry()
    registry.register(my_provider)

    # Discover capabilities
    chat_providers = registry.discover(Capability.CHAT)

    # Select models
    catalog = ModelCatalog()
    models = catalog.list_with_capability(Capability.STREAMING)
"""

from __future__ import annotations

from app.providers.capabilities import Capability, CapabilitySet
from app.providers.catalog import ModelCatalog, ModelMetadata
from app.providers.cost import CostCalculator, PricingModel, PricingTier
from app.providers.exceptions import (
    AuthenticationRequired,
    ContextWindowExceeded,
    InvalidModel,
    ProviderException,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimitExceeded,
    StreamingFailure,
    TokenLimitExceeded,
)
from app.providers.health import (
    CapabilityHealth,
    LatencyHealth,
    ProviderHealth,
    ProviderStatus,
)
from app.providers.metadata import ProviderMetadata
from app.providers.models import (
    AudioContent,
    ChatOptions,
    ChatResponse,
    ContentBlock,
    EmbeddingOptions,
    EmbeddingResponse,
    FinishReason,
    ImageContent,
    Message,
    MessageRole,
    Modality,
    ModelStatus,
    ProviderRequestOptions,
    ProviderResponse,
    TextContent,
    ToolCallContent,
    ToolResultContent,
    Usage,
)
from app.providers.registry import ProviderRegistry
from app.providers.streaming import (
    BackpressureManager,
    StreamChunk,
    StreamConsumer,
    StreamEventType,
    StreamingResponse,
    StreamPublisher,
)
from app.providers.tokenization import (
    TokenCounter,
    TokenEstimator,
    TokenUsage,
    UsageReport,
)

__all__ = [
    "AudioContent",
    "AuthenticationRequired",
    "BackpressureManager",
    "Capability",
    "CapabilityHealth",
    "CapabilitySet",
    "ChatOptions",
    "ChatResponse",
    "ContentBlock",
    "ContextWindowExceeded",
    "CostCalculator",
    "EmbeddingOptions",
    "EmbeddingResponse",
    "FinishReason",
    "ImageContent",
    "InvalidModel",
    "LatencyHealth",
    "Message",
    "MessageRole",
    "Modality",
    "ModelCatalog",
    "ModelMetadata",
    "ModelStatus",
    "PricingModel",
    "PricingTier",
    "ProviderException",
    "ProviderHealth",
    "ProviderMetadata",
    "ProviderRegistry",
    "ProviderRequestOptions",
    "ProviderResponse",
    "ProviderStatus",
    "ProviderTimeout",
    "ProviderUnavailable",
    "RateLimitExceeded",
    "StreamChunk",
    "StreamConsumer",
    "StreamEventType",
    "StreamPublisher",
    "StreamingFailure",
    "StreamingResponse",
    "TextContent",
    "TokenCounter",
    "TokenEstimator",
    "TokenLimitExceeded",
    "TokenUsage",
    "ToolCallContent",
    "ToolResultContent",
    "Usage",
    "UsageReport",
]
