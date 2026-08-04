"""Value objects for the Agent Runtime engine.

Re-exports shared value objects from ai.core for backward compatibility.
Agent-specific value objects remain defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.core.value_objects import ExecutionMetadata as AgentRunMetadata
from app.ai.core.value_objects import ProviderProfile as AgentProfile

__all__ = [
    "AgentCheckpoint",
    "AgentConfiguration",
    "AgentProfile",
    "AgentRunMetadata",
    "AgentStepResult",
]


@dataclass(frozen=True, slots=True)
class AgentConfiguration:
    """Full configuration for an agent run."""

    name: str = ""
    profile: AgentProfile = field(default_factory=AgentProfile)
    tools: tuple[str, ...] = ()
    max_steps: int = 10
    max_retries: int = 3
    timeout_seconds: int = 300
    checkpoint_interval: int = 5


@dataclass(frozen=True, slots=True)
class AgentStepResult:
    """Result of a single agent step execution."""

    step_id: str = ""
    step_index: int = 0
    tool_name: str = ""
    input_data: dict[str, object] = field(default_factory=dict)
    output_data: dict[str, object] = field(default_factory=dict)
    response: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error: str | None = None
    retry_count: int = 0


@dataclass(frozen=True, slots=True)
class AgentCheckpoint:
    """Serialized agent execution state for resume."""

    run_id: str
    checkpoint_number: int
    steps_completed: int
    steps_total: int
    last_step_index: int
    completed_step_ids: tuple[str, ...] = ()
    execution_context: dict[str, object] = field(default_factory=dict)
    accumulated_tokens_input: int = 0
    accumulated_tokens_output: int = 0
    accumulated_cost_usd: float = 0.0
    created_at: str = ""

    @property
    def completion_ratio(self) -> float:
        """Return completion ratio as a fraction."""
        if self.steps_total == 0:
            return 1.0
        return self.steps_completed / self.steps_total

    @property
    def is_complete(self) -> bool:
        """Return True if all steps have been completed."""
        return self.steps_completed >= self.steps_total
