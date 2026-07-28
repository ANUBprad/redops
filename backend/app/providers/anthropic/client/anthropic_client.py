"""Anthropic client — networking isolation layer.

All SDK interactions go through this wrapper. The rest of the
provider never imports anthropic directly.
"""

from __future__ import annotations

from typing import Any

from anthropic import AsyncAnthropic

from app.providers.anthropic.errors.mapping import map_anthropic_error

_MIN_KEY_LENGTH = 8


class AnthropicClient:
    """Thin wrapper around AsyncAnthropic that isolates SDK usage.

    Usage:
        client = AnthropicClient(api_key="sk-ant-...")
        response = await client.create_message(...)
        async for chunk in client.create_message_stream(...):
            ...

    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 0,
    ) -> None:
        """Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
            base_url: Custom base URL for the API.
            timeout: Request timeout in seconds.
            max_retries: SDK-level max retries (distinct from runtime retries).

        """
        self._client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )

    @property
    def api_key(self) -> str | None:
        """Return the API key (masked)."""
        key = self._client.api_key
        if key and len(key) > _MIN_KEY_LENGTH:
            return key[:4] + "..." + key[-4:]
        return None

    async def create_message(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        system: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Create a message.

        Args:
            model: Model identifier.
            messages: Anthropic-format messages.
            max_tokens: Maximum tokens to generate.
            system: Optional system prompt.
            **kwargs: Additional API parameters.

        Returns:
            Raw Anthropic Message object.

        Raises:
            ProviderException: Mapped from Anthropic SDK errors.

        """
        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if system is not None:
                params["system"] = system
            params.update(kwargs)
            return await self._client.messages.create(**params)
        except Exception as exc:
            raise map_anthropic_error(exc) from exc

    async def create_message_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        system: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Create a streaming message.

        Args:
            model: Model identifier.
            messages: Anthropic-format messages.
            max_tokens: Maximum tokens to generate.
            system: Optional system prompt.
            **kwargs: Additional API parameters.

        Returns:
            Async stream of Anthropic stream events.

        Raises:
            ProviderException: Mapped from Anthropic SDK errors.

        """
        try:
            params: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            if system is not None:
                params["system"] = system
            params.update(kwargs)
            return self._client.messages.stream(**params)
        except Exception as exc:
            raise map_anthropic_error(exc) from exc

    async def check_health(self) -> bool:
        """Check if the Anthropic API is reachable.

        Returns:
            True if the API is accessible.

        """
        try:
            await self._client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
        except Exception:  # noqa: BLE001
            return False
        else:
            return True

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
