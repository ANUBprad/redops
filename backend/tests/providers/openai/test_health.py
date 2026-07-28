"""Tests for OpenAI health contributor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.health.status import ProviderStatus
from app.providers.openai.health.contributor import OpenAIHealthContributor


class TestOpenAIHealthContributor:
    """Tests for OpenAIHealthContributor."""

    @pytest.mark.asyncio
    async def test_healthy(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=True)
        contributor = OpenAIHealthContributor(client)

        health = await contributor.check()
        assert health.status == ProviderStatus.HEALTHY
        assert health.is_healthy is True
        assert health.latency_ms is not None

    @pytest.mark.asyncio
    async def test_unhealthy(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=False)
        contributor = OpenAIHealthContributor(client)

        health = await contributor.check()
        assert health.status == ProviderStatus.UNHEALTHY
        assert health.is_healthy is False

    @pytest.mark.asyncio
    async def test_last_status(self) -> None:
        client = MagicMock()
        client.check_health = AsyncMock(return_value=True)
        contributor = OpenAIHealthContributor(client)

        await contributor.check()
        assert contributor.last_status == ProviderStatus.HEALTHY
