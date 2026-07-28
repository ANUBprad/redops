"""Stage type enumeration — leaf module with no internal dependencies.

Extracted into its own module to prevent circular imports between
stages, context, pipeline, and results modules.
"""

from __future__ import annotations

from enum import Enum, unique


@unique
class StageType(Enum):
    """Categorised type of a pipeline execution stage."""

    PLANNING = "planning"
    PREPARATION = "preparation"
    PROVIDER_INVOCATION = "provider_invocation"
    METRIC_DISPATCH = "metric_dispatch"
    AGGREGATION = "aggregation"
    PERSISTENCE = "persistence"
    COMPLETION = "completion"

    @property
    def order(self) -> int:
        """Return the canonical execution order for this stage type."""
        return _STAGE_ORDER[self]

    @property
    def description(self) -> str:
        """Return a human-readable description."""
        return _STAGE_DESCRIPTIONS[self]


_STAGE_ORDER: dict[StageType, int] = {
    StageType.PLANNING: 0,
    StageType.PREPARATION: 1,
    StageType.PROVIDER_INVOCATION: 2,
    StageType.METRIC_DISPATCH: 3,
    StageType.AGGREGATION: 4,
    StageType.PERSISTENCE: 5,
    StageType.COMPLETION: 6,
}

_STAGE_DESCRIPTIONS: dict[StageType, str] = {
    StageType.PLANNING: "Resolve execution plan from evaluation configuration",
    StageType.PREPARATION: "Prepare dataset items and provider connections",
    StageType.PROVIDER_INVOCATION: "Invoke provider models with prepared prompts",
    StageType.METRIC_DISPATCH: "Dispatch responses to metric evaluators",
    StageType.AGGREGATION: "Aggregate individual metric scores into summaries",
    StageType.PERSISTENCE: "Persist results and checkpoints",
    StageType.COMPLETION: "Finalize run state and emit completion events",
}
