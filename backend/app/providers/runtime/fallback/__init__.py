"""Fallback framework."""

from app.providers.runtime.fallback.fallback_chain import (
    FallbackChain,
    FallbackDecision,
    FallbackEntry,
    FallbackSelectionMode,
    FallbackState,
)

__all__ = [
    "FallbackChain",
    "FallbackDecision",
    "FallbackEntry",
    "FallbackSelectionMode",
    "FallbackState",
]
