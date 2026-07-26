"""ExecutionPlan — a complete, deterministic description of what to execute.

The plan references an EvaluationRun without mutating it.
It is versioned, serializable, and fully reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.evaluation.execution.pipeline.step import ExecutionStep
from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class PlanMetadata:
    """Metadata associated with an execution plan."""

    created_by: str = "system"
    description: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """A complete, immutable description of what to execute.

    The plan is the output of the planner and the input to the
    pipeline builder. It is deterministic (given the same run
    configuration, the same plan is produced) and reproducible
    (it carries all information needed to reconstruct execution).

    The plan references EvaluationRun by ID only — it never
    holds a mutable reference to domain entities.
    """

    plan_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    run_id: UUIDv7 = field(default_factory=UUIDv7)
    version: int = 1
    stages: tuple[StageType, ...] = ()
    steps: tuple[ExecutionStep, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: PlanMetadata = field(default_factory=PlanMetadata)
    total_items: int = 0

    # ── computed properties ────────────────────────────────────

    @property
    def step_count(self) -> int:
        """Return the total number of steps in the plan."""
        return len(self.steps)

    @property
    def stage_count(self) -> int:
        """Return the total number of stages in the plan."""
        return len(self.stages)

    @property
    def stage_types(self) -> list[StageType]:
        """Return stages sorted by canonical order."""
        return sorted(self.stages, key=lambda s: s.order)

    @property
    def steps_by_stage(self) -> dict[StageType, list[ExecutionStep]]:
        """Return steps grouped by their stage type."""
        result: dict[StageType, list[ExecutionStep]] = {}
        for step in self.steps:
            if step.stage_type not in result:
                result[step.stage_type] = []
            result[step.stage_type].append(step)
        return result

    def steps_for_stage(self, stage_type: StageType) -> list[ExecutionStep]:
        """Return steps for a specific stage type."""
        return [step for step in self.steps if step.stage_type == stage_type]

    # ── versioning ──────────────────────────────────────────────

    def with_version(self, version: int) -> ExecutionPlan:
        """Return a new plan with an updated version number.

        Args:
            version: New version number.

        Returns:
            A new ExecutionPlan with the incremented version.

        """
        return ExecutionPlan(
            plan_id=self.plan_id,
            run_id=self.run_id,
            version=version,
            stages=self.stages,
            steps=self.steps,
            created_at=self.created_at,
            metadata=self.metadata,
            total_items=self.total_items,
        )

    def increment_version(self) -> ExecutionPlan:
        """Return a new plan with the version incremented by 1."""
        return self.with_version(self.version + 1)

    # ── factory ─────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        run_id: UUIDv7,
        *,
        stages: Sequence[StageType] | None = None,
        steps: Sequence[ExecutionStep] | None = None,
        total_items: int = 0,
        version: int = 1,
        metadata: PlanMetadata | None = None,
    ) -> ExecutionPlan:
        """Create a new execution plan.

        Args:
            run_id: The ID of the parent evaluation run.
            stages: Ordered stage types.
            steps: Execution steps.
            total_items: Number of items in the dataset.
            version: Plan version.
            metadata: Optional plan metadata.

        Returns:
            A new ExecutionPlan instance.

        """
        return cls(
            run_id=run_id,
            stages=tuple(stages) if stages else (),
            steps=tuple(steps) if steps else (),
            total_items=total_items,
            version=version,
            metadata=metadata or PlanMetadata(),
        )
