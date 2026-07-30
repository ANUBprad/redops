"""Domain enums for the Agent Registry."""

from __future__ import annotations

from enum import Enum, unique


@unique
class AgentStatus(Enum):
    """Lifecycle status of an agent definition."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    ARCHIVED = "archived"

    @property
    def is_editable(self) -> bool:
        """Return True if the agent can be modified."""
        return self in _EDITABLE_STATES

    @property
    def is_terminal(self) -> bool:
        """Return True if this is a terminal state."""
        return self == AgentStatus.ARCHIVED


_EDITABLE_STATES: frozenset[AgentStatus] = frozenset(
    {
        AgentStatus.ACTIVE,
        AgentStatus.INACTIVE,
        AgentStatus.ERROR,
    }
)


@unique
class AgentType(Enum):
    """Type of agent determining its execution behavior."""

    LLM = "llm"
    TOOL = "tool"
    HYBRID = "hybrid"
    CUSTOM = "custom"
