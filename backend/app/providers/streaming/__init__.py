"""Streaming framework abstractions.

Provides provider-agnostic streaming types for real-time
response consumption without HTTP implementation.
"""

from __future__ import annotations

from app.providers.streaming.backpressure import BackpressureManager
from app.providers.streaming.chunk import StreamChunk, StreamEventType
from app.providers.streaming.consumer import StreamConsumer
from app.providers.streaming.publisher import StreamPublisher
from app.providers.streaming.response import StreamingResponse

__all__ = [
    "BackpressureManager",
    "StreamChunk",
    "StreamConsumer",
    "StreamEventType",
    "StreamPublisher",
    "StreamingResponse",
]
