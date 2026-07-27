"""Tests for runtime cache."""

import time

from app.providers.runtime.cache.runtime_cache import (
    CacheConfig,
    CacheEntry,
    CacheStats,
    RuntimeCache,
)


class TestRuntimeCache:
    """Tests for RuntimeCache."""

    def test_disabled_cache(self) -> None:
        cache = RuntimeCache(CacheConfig(enabled=False))
        cache.set("key", "value")
        assert cache.get("key") is None

    def test_set_and_get(self) -> None:
        cache = RuntimeCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_miss(self) -> None:
        cache = RuntimeCache()
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self) -> None:
        cache = RuntimeCache(CacheConfig(max_entries=2))
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_lru_access_preserves(self) -> None:
        cache = RuntimeCache(CacheConfig(max_entries=2))
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.set("c", 3)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_ttl_expiration(self) -> None:
        cache = RuntimeCache(CacheConfig(ttl_seconds=0.05))
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(0.1)
        assert cache.get("key") is None

    def test_invalidate(self) -> None:
        cache = RuntimeCache()
        cache.set("key", "value")
        assert cache.invalidate("key") is True
        assert cache.get("key") is None
        assert cache.invalidate("missing") is False

    def test_clear(self) -> None:
        cache = RuntimeCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.stats.size == 0

    def test_stats(self) -> None:
        cache = RuntimeCache()
        cache.set("a", 1)
        cache.get("a")
        cache.get("b")
        stats = cache.stats
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_build_key_deterministic(self) -> None:
        key1 = RuntimeCache.build_key("openai", "gpt-4", [{"role": "user", "content": "hi"}])
        key2 = RuntimeCache.build_key("openai", "gpt-4", [{"role": "user", "content": "hi"}])
        assert key1 == key2

    def test_build_key_different(self) -> None:
        key1 = RuntimeCache.build_key("openai", "gpt-4", [{"role": "user", "content": "hi"}])
        key2 = RuntimeCache.build_key("openai", "gpt-4", [{"role": "user", "content": "hello"}])
        assert key1 != key2

    def test_immutability(self) -> None:
        from datetime import UTC, datetime
        entry = CacheEntry(
            key="k", value="v", created_at=datetime.now(UTC), ttl_seconds=60
        )
        try:
            entry.key = "new"  # type: ignore[misc]
        except AttributeError:
            pass
        assert entry.key == "k"
