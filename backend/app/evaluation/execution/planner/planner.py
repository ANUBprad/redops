"""ExecutionPlanner — builds execution plans from evaluation runs.

This is the base planner that all concrete planners extend.
It provides common validation and plan construction logic
while deferring stage/step creation to subclasses.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.evaluation.execution.contracts.planner import ExecutionPlanner as ExecutionPlannerContract, PlanEstimate

if TYPE_CHECKING:
    from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
    from app.evaluation.execution.pipeline.plan import ExecutionPlan


class ExecutionPlanner(ExecutionPlannerContract, ABC):
    """Abstract base for execution planners.

    Extends the ExecutionPlanner contract with shared logic
    for plan construction, validation, and estimation.
    """

    @abstractmethod
    async def plan(self, run: EvaluationRun) -> ExecutionPlan:
        """Create an execution plan for the given run.

        Subclasses must implement the actual planning logic
        that analyses the run and produces stages and steps.
        """
        ...

    @abstractmethod
    async def validate_plan(self, plan: ExecutionPlan) -> list[str]:
        """Validate an execution plan for correctness.

        Subclasses may add domain-specific validation rules
        beyond the generic structural checks.
        """
        ...

    @abstractmethod
    async def estimate(self, run: EvaluationRun) -> PlanEstimate:
        """Provide a resource estimate for executing the given run."""
        ...
