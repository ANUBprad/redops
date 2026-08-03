"""AgentPlanner — creates execution plans for agent runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.domain.entities.agent_entities import AgentRun


@dataclass(frozen=True, slots=True)
class AgentExecutionPlan:
    """Execution plan for an agent run."""

    run_id: str
    total_steps: int
    tool_sequence: tuple[str, ...] = ()
    timeout_per_step: int = 60
    max_retries_per_step: int = 3
    metadata: dict[str, str] = field(default_factory=dict)


class AgentPlanner:
    """Creates execution plans from agent run configuration."""

    async def plan(self, run: AgentRun) -> AgentExecutionPlan:
        """Create an execution plan for the given run."""
        total_steps = run.config.max_steps
        timeout_per_step = min(
            run.config.timeout_seconds // max(total_steps, 1),
            120,
        )

        return AgentExecutionPlan(
            run_id=str(run.id),
            total_steps=total_steps,
            tool_sequence=run.config.tools,
            timeout_per_step=timeout_per_step,
            max_retries_per_step=run.config.max_retries,
        )

    async def validate_plan(self, plan: AgentExecutionPlan) -> list[str]:
        """Validate an execution plan for correctness."""
        errors: list[str] = []
        if plan.total_steps <= 0:
            errors.append(f"Invalid total_steps: {plan.total_steps}")
        if not plan.run_id:
            errors.append("Plan is missing run_id")
        if plan.timeout_per_step <= 0:
            errors.append(f"Invalid timeout_per_step: {plan.timeout_per_step}")
        return errors

    async def estimate(self, run: AgentRun) -> AgentPlanEstimate:
        """Provide a resource estimate for executing the run."""
        total_steps = run.config.max_steps
        estimated_tokens = total_steps * _ESTIMATED_TOKENS_PER_STEP
        estimated_cost = estimated_tokens * _ESTIMATED_COST_PER_TOKEN
        estimated_duration = total_steps * _ESTIMATED_SECONDS_PER_STEP

        return AgentPlanEstimate(
            estimated_steps=total_steps,
            estimated_duration_seconds=estimated_duration,
            estimated_cost_usd=estimated_cost,
            estimated_tokens=estimated_tokens,
        )


@dataclass(frozen=True, slots=True)
class AgentPlanEstimate:
    """Resource estimate for an agent run."""

    estimated_steps: int = 0
    estimated_duration_seconds: int = 0
    estimated_cost_usd: float = 0.0
    estimated_tokens: int = 0


_ESTIMATED_TOKENS_PER_STEP: int = 800
_ESTIMATED_COST_PER_TOKEN: float = 0.000004
_ESTIMATED_SECONDS_PER_STEP: int = 3
