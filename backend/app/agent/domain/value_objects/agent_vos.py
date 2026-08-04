"""Immutable value objects for the Agent Registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentName:
    """Validated name for an agent definition."""

    value: str

    def __post_init__(self) -> None:
        """Validate name invariants."""
        stripped = self.value.strip()
        if not stripped:
            msg = "Agent name cannot be empty"
            raise ValueError(msg)
        if len(stripped) > 255:
            msg = "Agent name cannot exceed 255 characters"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AgentDescription:
    """Optional description for an agent definition."""

    value: str | None = None

    def __post_init__(self) -> None:
        """Validate description invariants."""
        if self.value is not None and len(self.value) > 2000:
            msg = "Agent description cannot exceed 2000 characters"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AgentEndpoint:
    """Optional endpoint URL for a custom agent."""

    value: str | None = None

    def __post_init__(self) -> None:
        """Validate endpoint invariants."""
        if self.value is not None and not self.value.strip():
            msg = "Agent endpoint cannot be empty string"
            raise ValueError(msg)
