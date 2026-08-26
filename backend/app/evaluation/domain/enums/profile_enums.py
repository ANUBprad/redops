"""Domain enums for the Evaluation Profile aggregate."""

from __future__ import annotations

from enum import Enum, unique


@unique
class ProfileScope(Enum):
    """Scope of an evaluation profile."""

    SYSTEM = "system"
    PROJECT = "project"
    CUSTOM = "custom"
