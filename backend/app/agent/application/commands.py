"""Commands and queries for agent management."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CreateAgentCommand:
    """Command to create a new agent definition."""

    project_id: str
    name: str
    description: str | None = None
    agent_type: str = "llm"
    model: str = ""
    provider: str = ""
    capabilities: tuple[str, ...] = ()
    config: dict[str, object] = field(default_factory=dict)
    endpoint: str | None = None
    created_by: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateAgentCommand:
    """Command to update an existing agent definition."""

    agent_id: str
    name: str | None = None
    description: str | None = None
    agent_type: str | None = None
    model: str | None = None
    provider: str | None = None
    capabilities: tuple[str, ...] | None = None
    config: dict[str, object] | None = None
    endpoint: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteAgentCommand:
    """Command to delete an agent definition."""

    agent_id: str


@dataclass(frozen=True, slots=True)
class ActivateAgentCommand:
    """Command to activate an agent definition."""

    agent_id: str


@dataclass(frozen=True, slots=True)
class DeactivateAgentCommand:
    """Command to deactivate an agent definition."""

    agent_id: str


@dataclass(frozen=True, slots=True)
class ArchiveAgentCommand:
    """Command to archive an agent definition."""

    agent_id: str


@dataclass(frozen=True, slots=True)
class GetAgentQuery:
    """Query to retrieve a single agent by ID."""

    agent_id: str


@dataclass(frozen=True, slots=True)
class ListAgentsQuery:
    """Query to list agents with filtering and pagination."""

    project_id: str | None = None
    agent_type: str | None = None
    status: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20
