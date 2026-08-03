"""Agent run state machine."""

from __future__ import annotations

from app.agents.domain.enums.agent_enums import AgentRunStatus

_VALID_TRANSITIONS: dict[AgentRunStatus, frozenset[AgentRunStatus]] = {
    AgentRunStatus.CREATED: frozenset({AgentRunStatus.QUEUED}),
    AgentRunStatus.QUEUED: frozenset({AgentRunStatus.STARTING, AgentRunStatus.CANCELLED}),
    AgentRunStatus.STARTING: frozenset(
        {AgentRunStatus.RUNNING, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED}
    ),
    AgentRunStatus.RUNNING: frozenset(
        {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.PAUSED,
            AgentRunStatus.TIMEDOUT,
            AgentRunStatus.CANCELLING,
        }
    ),
    AgentRunStatus.PAUSED: frozenset({AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED}),
    AgentRunStatus.CANCELLING: frozenset({AgentRunStatus.CANCELLED}),
}


class AgentRunStateMachine:
    """State machine for agent run lifecycle transitions."""

    def can_transition(
        self,
        current: AgentRunStatus,
        target: AgentRunStatus,
    ) -> bool:
        """Check if a transition is valid."""
        valid = _VALID_TRANSITIONS.get(current, frozenset())
        return target in valid
