"""Capability system for provider feature discovery.

Provides a generic, queryable capability model that allows the
Evaluation Engine to discover what features each provider supports
without coupling to provider-specific implementations.
"""

from __future__ import annotations

from app.providers.capabilities.capability import Capability
from app.providers.capabilities.capability_set import CapabilitySet

__all__ = ["Capability", "CapabilitySet"]
