"""Tests for the OpenAI embedding boundary.

Covers the adapter (SDK response mapping), provider delegation, and
capability declaration for text embeddings.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.capabilities.capability import Capability
from app.providers.models.options import EmbeddingOptions
from app.providers.models.responses import EmbeddingResponse, Usage
from app.providers.openai.adapters.contracts import OpenAIEmbeddingAdapter
from app.providers.openai.client.openai_client import OpenAIClient
from app.providers.openai.provider import OpenAIProvider


def _make_sdk_embedding_response(
    *,
    vector: list[float] | None = None,
    model: str = "text-embedding-3-small",
) -> MagicMock:
    """Create a mock raw OpenAI embedding response."""
    vector = vector if vector is not None else [0.1, 0.2, 0.3]
    response = MagicMock()
    response.model = model

    item = MagicMock()
    item.embedding = vector
    response.data = [item]

    usage = MagicMock()
    usage.prompt_tokens = 4
    usage.completion_tokens = 0
    usage.total_tokens = 4
    usage.prompt_tokens_details = None
    usage.completion_tokens_details = None
    response.usage = usage

    return response


class TestOpenAIEmbeddingAdapter:
    """Tests for OpenAIEmbeddingAdapter."""

    @pytest.mark.asyncio
    async def test_embed_maps_sdk_response(self) -> None:
        client = MagicMock(spec=OpenAIClient)
        client.create_embedding = AsyncMock(
            return_value=_make_sdk_embedding_response(
                vector=[0.5, -0.25, 0.75],
                model="text-embedding-3-small",
            ),
        )
        adapter = OpenAIEmbeddingAdapter(client)

        result = await adapter.embed(["hello world"], model="text-embedding-3-small")

        assert isinstance(result, EmbeddingResponse)
        assert result.embedding == (0.5, -0.25, 0.75)
        assert result.dimensions == 3
        assert result.model == "text-embedding-3-small"
        assert result.usage.input_tokens == 4

        client.create_embedding.assert_awaited_once_with(
            model="text-embedding-3-small",
            texts=["hello world"],
        )

    @pytest.mark.asyncio
    async def test_embed_passes_dimensions_option(self) -> None:
        client = MagicMock(spec=OpenAIClient)
        client.create_embedding = AsyncMock(
            return_value=_make_sdk_embedding_response(vector=[0.1] * 256),
        )
        adapter = OpenAIEmbeddingAdapter(client)

        await adapter.embed(
            ["hello"],
            model="text-embedding-3-large",
            options=EmbeddingOptions(dimensions=256),
        )

        client.create_embedding.assert_awaited_once_with(
            model="text-embedding-3-large",
            texts=["hello"],
            dimensions=256,
            encoding_format="float",
        )

    @pytest.mark.asyncio
    async def test_embed_no_options_sends_no_extra_params(self) -> None:
        client = MagicMock(spec=OpenAIClient)
        client.create_embedding = AsyncMock(
            return_value=_make_sdk_embedding_response(),
        )
        adapter = OpenAIEmbeddingAdapter(client)

        await adapter.embed(["hello"], model="text-embedding-3-small", options=None)

        client.create_embedding.assert_awaited_once_with(
            model="text-embedding-3-small",
            texts=["hello"],
        )

    @pytest.mark.asyncio
    async def test_embed_propagates_client_errors(self) -> None:
        """SDK-level failures surface instead of being swallowed."""
        client = MagicMock(spec=OpenAIClient)
        client.create_embedding = AsyncMock(side_effect=ValueError("sdk down"))
        adapter = OpenAIEmbeddingAdapter(client)

        with pytest.raises(ValueError, match="sdk down"):
            await adapter.embed(["hello"], model="text-embedding-3-small")


class TestOpenAIProviderEmbedding:
    """Provider-level embedding wiring."""

    def test_declares_embedding_capabilities(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        caps = provider.capabilities()
        assert caps.supports(Capability.EMBEDDING)
        assert caps.supports(Capability.EMBEDDING_DIMENSIONS)

    def test_implements_embedding_contract(self) -> None:
        from app.providers.contracts.embedding import EmbeddingProvider as Contract

        provider = OpenAIProvider(api_key="test-key")
        assert isinstance(provider, Contract)

    @pytest.mark.asyncio
    async def test_embed_delegates_to_adapter(self) -> None:
        provider = OpenAIProvider(api_key="test-key")
        provider._embedding_adapter = MagicMock()
        provider._embedding_adapter.embed = AsyncMock(
            return_value=EmbeddingResponse(
                model="text-embedding-3-small",
                provider="openai",
                usage=Usage(),
                embedding=(1.0, 0.0),
                dimensions=2,
            ),
        )

        result = await provider.embed(
            ["text"],
            model="text-embedding-3-small",
            options=EmbeddingOptions(dimensions=2),
        )

        assert result.embedding == (1.0, 0.0)
        assert result.dimensions == 2
        provider._embedding_adapter.embed.assert_awaited_once_with(
            ["text"],
            model="text-embedding-3-small",
            options=EmbeddingOptions(dimensions=2),
        )
