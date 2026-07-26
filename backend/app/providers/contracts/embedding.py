"""Embedding provider contract.

Defines the interface for providers that support text
embedding generation.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.models.options import EmbeddingOptions
    from app.providers.models.responses import EmbeddingResponse


class EmbeddingProvider:
    """Interface for embedding providers.

    Providers that support text embedding must implement
    this interface for embedding-based evaluations.
    """

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
        options: EmbeddingOptions | None = None,
    ) -> EmbeddingResponse:
        """Generate embeddings for the given texts.

        Args:
            texts: The input texts to embed.
            model: The model identifier to use.
            options: Optional embedding parameters.

        Returns:
            The embedding response with vectors.

        Raises:
            InvalidModel: If the model is not recognized.
            ProviderUnavailable: If the provider is down.

        """
