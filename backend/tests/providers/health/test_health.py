"""Tests for health integration."""

from __future__ import annotations

from app.providers.capabilities.capability import Capability
from app.providers.health.capability_health import CapabilityHealth
from app.providers.health.latency_health import LatencyHealth
from app.providers.health.provider_health import ProviderHealth
from app.providers.health.status import ProviderStatus


class TestProviderStatus:
    def test_values(self) -> None:
        assert ProviderStatus.HEALTHY == "healthy"
        assert ProviderStatus.DEGRADED == "degraded"
        assert ProviderStatus.UNHEALTHY == "unhealthy"


class TestProviderHealth:
    def test_is_healthy(self) -> None:
        h = ProviderHealth(provider_name="test", status=ProviderStatus.HEALTHY)
        assert h.is_healthy

    def test_is_not_healthy(self) -> None:
        h = ProviderHealth(provider_name="test", status=ProviderStatus.UNHEALTHY)
        assert not h.is_healthy

    def test_is_available_healthy(self) -> None:
        h = ProviderHealth(provider_name="test", status=ProviderStatus.HEALTHY)
        assert h.is_available

    def test_is_available_degraded(self) -> None:
        h = ProviderHealth(provider_name="test", status=ProviderStatus.DEGRADED)
        assert h.is_available

    def test_is_not_available_unhealthy(self) -> None:
        h = ProviderHealth(provider_name="test", status=ProviderStatus.UNHEALTHY)
        assert not h.is_available


class TestCapabilityHealth:
    def test_is_operational(self) -> None:
        ch = CapabilityHealth(capability=Capability.CHAT, status=ProviderStatus.HEALTHY)
        assert ch.is_operational

    def test_is_not_operational(self) -> None:
        ch = CapabilityHealth(capability=Capability.CHAT, status=ProviderStatus.UNHEALTHY)
        assert not ch.is_operational


class TestLatencyHealth:
    def test_healthy_latency(self) -> None:
        lh = LatencyHealth(
            provider_name="test",
            p50_ms=100,
            p95_ms=500,
            p99_ms=1000,
            sample_count=100,
        )
        assert lh.status == ProviderStatus.HEALTHY
        assert lh.is_healthy

    def test_degraded_latency(self) -> None:
        lh = LatencyHealth(
            provider_name="test",
            p50_ms=2000,
            p95_ms=3000,
            p99_ms=5000,
            sample_count=100,
        )
        assert lh.status == ProviderStatus.DEGRADED

    def test_unhealthy_latency(self) -> None:
        lh = LatencyHealth(
            provider_name="test",
            p50_ms=5000,
            p95_ms=8000,
            p99_ms=10000,
            sample_count=100,
        )
        assert lh.status == ProviderStatus.UNHEALTHY

    def test_unknown_when_no_samples(self) -> None:
        lh = LatencyHealth(provider_name="test", sample_count=0)
        assert lh.status == ProviderStatus.UNKNOWN
