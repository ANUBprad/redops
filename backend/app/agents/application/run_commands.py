"""Commands and queries for agent run management."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateAgentRunCommand:
    """Command to create a new agent run."""

    agent_name: str = ""
    agent_definition_id: str | None = None
    provider: str = ""
    model: str = ""
    tools: tuple[str, ...] = ()
    max_steps: int = 10
    timeout_seconds: int = 300
    project_id: str | None = None
    created_by: str | None = None
    tags: tuple[str, ...] = ()
    workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class QueueAgentRunCommand:
    """Command to queue a run for execution."""

    run_id: str


@dataclass(frozen=True, slots=True)
class StartAgentRunCommand:
    """Command to start a queued run."""

    run_id: str
    total_steps: int


@dataclass(frozen=True, slots=True)
class UpdateAgentRunProgressCommand:
    """Command to update run progress."""

    run_id: str
    steps_completed: int = 0
    steps_failed: int = 0
    token_input: int = 0
    token_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass(frozen=True, slots=True)
class CompleteAgentRunCommand:
    """Command to mark a run as completed."""

    run_id: str


@dataclass(frozen=True, slots=True)
class FailAgentRunCommand:
    """Command to mark a run as failed."""

    run_id: str
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True, slots=True)
class CancelAgentRunCommand:
    """Command to cancel a run."""

    run_id: str
    reason: str = "user_cancelled"
    force: bool = False


@dataclass(frozen=True, slots=True)
class RetryAgentRunCommand:
    """Command to retry a failed run."""

    run_id: str


@dataclass(frozen=True, slots=True)
class GetAgentRunQuery:
    """Query to retrieve a single run by ID."""

    run_id: str


@dataclass(frozen=True, slots=True)
class ListAgentRunsQuery:
    """Query to list runs with filtering and pagination."""

    agent_name: str | None = None
    status: str | None = None
    provider: str | None = None
    model: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20
