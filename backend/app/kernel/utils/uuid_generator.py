"""UUID generator abstraction for deterministic identity generation in tests.

Production implementations should generate UUIDv7 (time-sortable) values.
Test implementations can return fixed or sequential values.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod


class UUIDGenerator(ABC):
    """Abstract UUID generator.

    Use this interface everywhere instead of calling uuid.uuid4()
    directly. This enables deterministic ID values in tests.
    """

    @abstractmethod
    def generate(self) -> uuid.UUID:
        """Generate and return a new UUID."""
        ...


class RandomUUIDGenerator(UUIDGenerator):
    """Production UUID generator using uuid4."""

    def generate(self) -> uuid.UUID:
        return uuid.uuid4()


class SequentialUUIDGenerator(UUIDGenerator):
    """Sequential UUID generator for testing.

    Produces UUIDs from a deterministic counter, making tests reproducible.
    """

    def __init__(self, start: int = 1) -> None:
        self._counter = start

    def generate(self) -> uuid.UUID:
        result = uuid.UUID(int=self._counter)
        self._counter += 1
        return result
