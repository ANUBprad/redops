"""Model catalog.

Provides immutable model metadata and a queryable catalog
for discovering available models across providers.
"""

from __future__ import annotations

from app.providers.catalog.catalog import ModelCatalog
from app.providers.catalog.model import ModelMetadata

__all__ = ["ModelCatalog", "ModelMetadata"]
