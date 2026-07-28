"""OpenAI client — networking isolation layer.

All SDK interactions go through this wrapper. The rest of the
provider never imports openai directly.
"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.providers.openai.errors.mapping import map_openai_error

_MIN_KEY_LENGTH = 8


class OpenAIClient:
    """Thin wrapper around AsyncOpenAI that isolates SDK usage.

    Usage:
        client = OpenAIClient(api_key="sk-...")
        response = await client.create_chat_completion(...)
        async for chunk in client.create_chat_stream(...):
            ...

    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        timeout: float = 120.0,
        max_retries: int = 0,
    ) -> None:
        """Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key. Falls back to OPENAI_API_KEY env var.
            base_url: Custom base URL for the API.
            organization: OpenAI organization ID.
            timeout: Request timeout in seconds.
            max_retries: SDK-level max retries (distinct from runtime retries).

        """
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
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

    async def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        """Create a chat completion.

        Args:
            model: Model identifier.
            messages: OpenAI-format messages.
            **kwargs: Additional API parameters.

        Returns:
            Raw OpenAI ChatCompletion object.

        Raises:
            ProviderException: Mapped from OpenAI SDK errors.

        """
        try:
            return await self._client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
        except Exception as exc:
            raise map_openai_error(exc) from exc

    async def create_chat_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> Any:
        """Create a streaming chat completion.

        Args:
            model: Model identifier.
            messages: OpenAI-format messages.
            **kwargs: Additional API parameters.

        Returns:
            Async stream of OpenAI ChatCompletionChunk objects.

        Raises:
            ProviderException: Mapped from OpenAI SDK errors.

        """
        try:
            return await self._client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs,
            )
        except Exception as exc:
            raise map_openai_error(exc) from exc

    async def create_embedding(
        self,
        *,
        model: str,
        texts: list[str],
        **kwargs: Any,
    ) -> Any:
        """Create embeddings.

        Args:
            model: Model identifier.
            texts: Texts to embed.
            **kwargs: Additional API parameters.

        Returns:
            Raw OpenAI embedding response.

        Raises:
            ProviderException: Mapped from OpenAI SDK errors.

        """
        try:
            return await self._client.embeddings.create(
                model=model,
                input=texts,
                **kwargs,
            )
        except Exception as exc:
            raise map_openai_error(exc) from exc

    async def check_health(self) -> bool:
        """Check if the OpenAI API is reachable.

        Returns:
            True if the API is accessible.

        """
        try:
            await self._client.models.list()
        except Exception:
            return False
        else:
            return True

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()
