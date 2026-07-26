"""Backpressure management for streaming.

Provides abstractions for controlling the flow rate
of streaming data between producers and consumers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackpressureManager:
    """Manages backpressure for streaming consumers.

    When a consumer cannot keep up with the producer,
    the backpressure manager buffers chunks and signals
    the producer to slow down.

    Attributes:
        high_watermark: Buffer size that triggers pause.
        low_watermark: Buffer size that triggers resume.

    """

    high_watermark: int = 100
    low_watermark: int = 20
    _buffer: list[Any] = field(default_factory=list, init=False)
    _paused: bool = field(default=False, init=False)
    _pause_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    def __post_init__(self) -> None:
        """Initialize the pause event (not paused initially)."""
        self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        """Check if the publisher should pause."""
        return self._paused

    @property
    def buffer_size(self) -> int:
        """Return current buffer size."""
        return len(self._buffer)

    def should_pause(self) -> bool:
        """Check if backpressure requires pausing."""
        if not self._paused and len(self._buffer) >= self.high_watermark:
            self._paused = True
            self._pause_event.clear()
            return True
        return False

    def should_resume(self) -> bool:
        """Check if pressure has been relieved."""
        if self._paused and len(self._buffer) <= self.low_watermark:
            self._paused = False
            self._pause_event.set()
            return True
        return False

    async def wait_if_paused(self) -> None:
        """Wait until pressure is relieved."""
        await self._pause_event.wait()

    def add_to_buffer(self, item: object) -> None:
        """Add an item to the buffer."""
        self._buffer.append(item)

    def take_from_buffer(self) -> object | None:
        """Remove and return an item from the buffer."""
        if self._buffer:
            item = self._buffer.pop(0)
            self.should_resume()
            return item
        return None

    def clear_buffer(self) -> None:
        """Clear the buffer."""
        self._buffer.clear()
        if self._paused:
            self._paused = False
            self._pause_event.set()
