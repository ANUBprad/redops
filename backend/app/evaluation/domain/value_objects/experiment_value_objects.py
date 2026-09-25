"""Immutable value objects for the Experiment aggregate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExperimentName:
    """Validated name for an experiment."""

    value: str

    def __post_init__(self) -> None:
        """Validate name invariants."""
        stripped = self.value.strip()
        if not stripped:
            msg = "Experiment name cannot be empty"
            raise ValueError(msg)
        if len(stripped) > 255:
            msg = "Experiment name cannot exceed 255 characters"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ExperimentDescription:
    """Optional description for an experiment."""

    value: str | None = None

    def __post_init__(self) -> None:
        """Validate description invariants."""
        if self.value is not None and len(self.value) > 2000:
            msg = "Experiment description cannot exceed 2000 characters"
            raise ValueError(msg)
