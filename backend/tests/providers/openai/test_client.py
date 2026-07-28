"""Tests for OpenAI client wrapper."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.providers.openai.client.openai_client import OpenAIClient
from app.providers.exceptions.auth import AuthenticationRequired


class TestOpenAIClient:
    """Tests for OpenAIClient."""

    def test_api_key_masked(self) -> None:
        client = OpenAIClient(api_key="sk-1234567890abcdef")
        assert client.api_key == "sk-1...cdef"

    def test_api_key_short(self) -> None:
        client = OpenAIClient(api_key="sk-12")
        assert client.api_key is None

    @pytest.mark.asyncio
    async def test_create_chat_completion_success(self) -> None:
        client = OpenAIClient(api_key="test-key")
        mock_response = MagicMock()
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await client.create_chat_completion(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_create_chat_completion_error(self) -> None:
        from openai import AuthenticationError
        from unittest.mock import MagicMock

        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {}
        resp.request = MagicMock()
        resp.request.url = "https://api.openai.com"
        resp.content = b'{"error": {"message": "Invalid key"}}'

        client = OpenAIClient(api_key="test-key")
        error = AuthenticationError(
            message="Invalid key",
            response=resp,
            body=None,
        )
        client._client.chat.completions.create = AsyncMock(side_effect=error)

        with pytest.raises(AuthenticationRequired):
            await client.create_chat_completion(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Hi"}],
            )

    @pytest.mark.asyncio
    async def test_check_health_success(self) -> None:
        client = OpenAIClient(api_key="test-key")
        mock_models = MagicMock()
        mock_models.data = []
        client._client.models.list = AsyncMock(return_value=mock_models)

        assert await client.check_health() is True

    @pytest.mark.asyncio
    async def test_check_health_failure(self) -> None:
        client = OpenAIClient(api_key="test-key")
        client._client.models.list = AsyncMock(side_effect=Exception("connection failed"))

        assert await client.check_health() is False
