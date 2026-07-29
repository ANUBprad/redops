"""Tests for Anthropic health contributor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.anthropic.health.contributor import AnthropicHealthContributor
from app.providers.health.status import ProviderStatus


class TestAnthropicHealthContributor:
    """Tests for AnthropicHealthContributor."""

    @pytest.mark.asyncio
    async def test_healthy(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=True)
        contributor = AnthropicHealthContributor(client)

        health = await contributor.check()
        assert health.status == ProviderStatus.HEALTHY
        assert health.is_healthy is True
        assert health.latency_ms is not None
        assert health.latency_ms >= 0
        assert health.provider_name == "anthropic"
        assert "reachable" in health.message.lower()

    @pytest.mark.asyncio
    async def test_unhealthy(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=False)
        contributor = AnthropicHealthContributor(client)

        health = await contributor.check()
        assert health.status == ProviderStatus.UNHEALTHY
        assert health.is_healthy is False
        assert "unreachable" in health.message.lower()

    @pytest.mark.asyncio
    async def test_last_status(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=True)
        contributor = AnthropicHealthContributor(client)

        await contributor.check()
        assert contributor.last_status == ProviderStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_last_status_unhealthy(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=False)
        contributor = AnthropicHealthContributor(client)

        await contributor.check()
        assert contributor.last_status == ProviderStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_last_status_before_check(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=True)
        contributor = AnthropicHealthContributor(client)

        assert contributor.last_status == ProviderStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_last_latency_ms(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=True)
        contributor = AnthropicHealthContributor(client)

        assert contributor.last_latency_ms is None

        await contributor.check()
        assert contributor.last_latency_ms is not None
        assert contributor.last_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_last_check_time(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=True)
        contributor = AnthropicHealthContributor(client)

        health = await contributor.check()
        assert health.last_check is not None

    @pytest.mark.asyncio
    async def test_multiple_checks(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(side_effect=[True, False, True])
        contributor = AnthropicHealthContributor(client)

        await contributor.check()
        assert contributor.last_status == ProviderStatus.HEALTHY

        await contributor.check()
        assert contributor.last_status == ProviderStatus.UNHEALTHY

        await contributor.check()
        assert contributor.last_status == ProviderStatus.HEALTHY
