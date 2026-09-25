"""Immutable value objects for the Evaluation Profile aggregate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProfileName:
    """Validated name for an evaluation profile."""

    value: str

    def __post_init__(self) -> None:
        """Validate name invariants."""
        stripped = self.value.strip()
        if not stripped:
            msg = "Profile name cannot be empty"
            raise ValueError(msg)
        if len(stripped) > 255:
            msg = "Profile name cannot exceed 255 characters"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ProfileDescription:
    """Optional description for an evaluation profile."""

    value: str | None = None

    def __post_init__(self) -> None:
        """Validate description invariants."""
        if self.value is not None and len(self.value) > 2000:
            msg = "Profile description cannot exceed 2000 characters"
            raise ValueError(msg)
