"""Model selection strategies.

Provides pluggable strategies for selecting models based on
cost, performance, capabilities, and health criteria.
"""

from __future__ import annotations

from app.providers.selection.strategy import SelectionStrategy

__all__ = ["SelectionStrategy"]
