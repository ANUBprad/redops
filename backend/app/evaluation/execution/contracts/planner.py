"""ExecutionPlanner contract — transforms a run into an execution plan.

The planner is responsible for analysing an EvaluationRun and
producing a complete, deterministic ExecutionPlan.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
    from app.evaluation.execution.pipeline.plan import ExecutionPlan


class ExecutionPlanner(ABC):
    """Contract for creating execution plans from evaluation runs.

    Implementations analyse the run's configuration, dataset size,
    metrics, and profile to produce a plan describing exactly
    what will be executed.
    """

    @abstractmethod
    async def plan(self, run: EvaluationRun) -> ExecutionPlan:
        """Create an execution plan for the given run.

        Args:
            run: The evaluation run to plan for.

        Returns:
            A complete, deterministic ExecutionPlan.

        """
        ...

    @abstractmethod
    async def validate_plan(self, plan: ExecutionPlan) -> list[str]:
        """Validate an execution plan for correctness.

        Args:
            plan: The plan to validate.

        Returns:
            A list of validation errors. Empty means valid.

        """
        ...

    @abstractmethod
    async def estimate(self, run: EvaluationRun) -> PlanEstimate:
        """Provide a resource estimate for executing the given run.

        Args:
            run: The evaluation run to estimate for.

        Returns:
            A PlanEstimate with projected resource usage.

        """
        ...


class PlanEstimate:
    """Resource estimate for executing an evaluation run."""

    def __init__(
        self,
        *,
        estimated_steps: int = 0,
        estimated_duration_seconds: int = 0,
        estimated_cost_usd: float = 0.0,
        estimated_tokens: int = 0,
    ) -> None:
        """Initialize a plan estimate.

        Args:
            estimated_steps: Projected number of steps.
            estimated_duration_seconds: Projected duration.
            estimated_cost_usd: Projected cost.
            estimated_tokens: Projected token usage.

        """
        self.estimated_steps = estimated_steps
        self.estimated_duration_seconds = estimated_duration_seconds
        self.estimated_cost_usd = estimated_cost_usd
        self.estimated_tokens = estimated_tokens

    def __repr__(self) -> str:
        return (
            f"PlanEstimate(steps={self.estimated_steps}, "
            f"duration={self.estimated_duration_seconds}s, "
            f"cost=${self.estimated_cost_usd:.4f}, "
            f"tokens={self.estimated_tokens})"
        )
