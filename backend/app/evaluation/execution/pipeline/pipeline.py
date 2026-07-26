"""ExecutionPipeline — the ordered container of stages and steps.

A pipeline is built from an ExecutionPlan and contains the
stages and steps in executable order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.evaluation.execution.pipeline.plan import ExecutionPlan
from app.evaluation.execution.stages.stage import ExecutionStage
from app.evaluation.execution.stages.types import StageType
from app.kernel.entities.base import UUIDv7

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class ExecutionPipeline:
    """An ordered container of execution stages and steps.

    The pipeline is the runtime representation of an ExecutionPlan.
    It holds references to stage instances and their assigned steps
    in the correct execution order.
    """

    pipeline_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    plan: ExecutionPlan | None = None
    stages: tuple[ExecutionStage, ...] = ()
    stage_order: tuple[StageType, ...] = ()

    # ── computed properties ────────────────────────────────────

    @property
    def run_id(self) -> UUIDv7 | None:
        """Return the run ID from the associated plan."""
        return self.plan.run_id if self.plan else None

    @property
    def stage_count(self) -> int:
        """Return the number of stages in the pipeline."""
        return len(self.stages)

    @property
    def stage_types(self) -> list[StageType]:
        """Return the ordered stage types."""
        return list(self.stage_order) if self.stage_order else []

    @property
    def stages_by_type(self) -> dict[StageType, ExecutionStage]:
        """Return stages indexed by their type."""
        return {stage.stage_type: stage for stage in self.stages}

    # ── stage lookup ───────────────────────────────────────────

    def get_stage(self, stage_type: StageType) -> ExecutionStage | None:
        """Return the stage instance for the given type.

        Args:
            stage_type: The type of stage to look up.

        Returns:
            The matching stage, or None.

        """
        for stage in self.stages:
            if stage.stage_type == stage_type:
                return stage
        return None

    def has_stage(self, stage_type: StageType) -> bool:
        """Return True if the pipeline contains the given stage type.

        Args:
            stage_type: The type of stage to check.

        Returns:
            True if the stage exists.

        """
        return stage_type in {s.stage_type for s in self.stages}
