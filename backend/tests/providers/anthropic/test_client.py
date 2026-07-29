"""Tests for Anthropic client wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.anthropic.client.anthropic_client import AnthropicClient
from app.providers.exceptions.auth import AuthenticationRequired


class TestAnthropicClient:
    """Tests for AnthropicClient."""

    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    def test_api_key_masked(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.api_key = "sk-ant-1234567890abcdef"
        mock_cls.return_value = mock_instance
        client = AnthropicClient(api_key="sk-ant-1234567890abcdef")
        assert client.api_key == "sk-a...cdef"

    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    def test_api_key_short(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.api_key = "sk-12"
        mock_cls.return_value = mock_instance
        client = AnthropicClient(api_key="sk-12")
        assert client.api_key is None

    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    def test_api_key_none(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.api_key = None
        mock_cls.return_value = mock_instance
        client = AnthropicClient(api_key=None)
        assert client.api_key is None

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_create_message_success(self, mock_cls):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        result = await client.create_message(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024,
        )
        assert result == mock_response
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_create_message_with_system(self, mock_cls):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        await client.create_message(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024,
            system="Be helpful",
        )
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "Be helpful"

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_create_message_error(self, mock_cls):
        from anthropic import AuthenticationError

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.headers = {}
        mock_resp.request = MagicMock()
        mock_resp.content = b'{"error": {"message": "Invalid key"}}'

        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(
            side_effect=AuthenticationError(
                message="Invalid key",
                response=mock_resp,
                body=None,
            )
        )
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        with pytest.raises(AuthenticationRequired):
            await client.create_message(
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024,
            )

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_create_message_stream_success(self, mock_cls):
        mock_stream = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(return_value=mock_stream)
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        result = await client.create_message_stream(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024,
        )
        assert result == mock_stream
        mock_client.messages.stream.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_create_message_stream_error(self, mock_cls):
        from anthropic import RateLimitError

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        mock_resp.request = MagicMock()
        mock_resp.content = b'{"error": {"message": "Rate limited"}}'

        mock_client = MagicMock()
        mock_client.messages.stream = MagicMock(
            side_effect=RateLimitError(
                message="Rate limited",
                response=mock_resp,
                body=None,
            )
        )
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        from app.providers.exceptions.rate_limit import RateLimitExceeded

        with pytest.raises(RateLimitExceeded):
            await client.create_message_stream(
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=1024,
            )

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_check_health_success(self, mock_cls):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=MagicMock())
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        assert await client.check_health() is True

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_check_health_failure(self, mock_cls):
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("connection failed"))
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        assert await client.check_health() is False

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_close(self, mock_cls):
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        await client.close()
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.providers.anthropic.client.anthropic_client.AsyncAnthropic")
    async def test_create_message_with_kwargs(self, mock_cls):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        client = AnthropicClient(api_key="test-key")
        await client.create_message(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1024,
            temperature=0.7,
        )
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7
