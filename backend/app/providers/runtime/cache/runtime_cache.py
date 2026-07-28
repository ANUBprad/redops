"""Cache abstractions — provider response caching."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheConfig:
    """Immutable cache configuration.

    Attributes:
        max_entries: Maximum cache entries.
        ttl_seconds: Time-to-live for entries.
        enabled: Whether caching is active.

    """

    max_entries: int = 1000
    ttl_seconds: float = 300.0
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Immutable cache entry."""

    key: str
    value: Any
    created_at: datetime
    ttl_seconds: float
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Return True if entry has expired."""
        return datetime.now(UTC) > self.created_at + timedelta(seconds=self.ttl_seconds)


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Immutable cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class RuntimeCache:
    """In-memory LRU cache for provider responses.

    Usage:
        cache = RuntimeCache(config)
        cached = cache.get(key)
        if cached is None:
            response = await call_provider(...)
            cache.set(key, response)

    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize cache."""
        self._config = config or CacheConfig()
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    @property
    def stats(self) -> CacheStats:
        """Return cache statistics."""
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            size=len(self._entries),
        )

    def get(self, key: str) -> Any | None:
        """Get value by key.

        Returns:
            Cached value or None if miss/expired.

        """
        if not self._config.enabled:
            return None

        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            self._entries.pop(key, None)
            self._misses += 1
            return None

        self._entries.move_to_end(key)
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """Set a cache entry."""
        if not self._config.enabled:
            return

        if key in self._entries:
            self._entries.move_to_end(key)
        elif len(self._entries) >= self._config.max_entries:
            self._entries.popitem(last=False)
            self._evictions += 1

        self._entries[key] = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(UTC),
            ttl_seconds=ttl_seconds or self._config.ttl_seconds,
        )

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific key."""
        if key in self._entries:
            self._entries.pop(key)
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._entries.clear()

    @staticmethod
    def build_key(
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Build a deterministic cache key."""
        payload = json.dumps(
            {"provider": provider, "model": model, "messages": messages, **kwargs},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:32]
