"""Trajectory evaluator — orchestrates trajectory evaluation.

Evaluates agent trajectories by registering trajectory metrics with
the MetricEngine and running them against the trajectory data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.evaluation.metrics.domain import (
    MetricInput,
    MetricResult,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.trajectories import (
    TrajectoryCompletenessMetric,
    TrajectoryEfficiencyMetric,
    TrajectoryErrorRecoveryMetric,
    TrajectoryToolSelectionMetric,
)

logger = logging.getLogger(__name__)

TRAJECTORY_METRIC_NAMES = (
    "trajectory_completeness",
    "trajectory_efficiency",
    "trajectory_error_recovery",
    "trajectory_tool_selection",
)


@dataclass(frozen=True, slots=True)
class TrajectoryEvaluationResult:
    """Result of evaluating a single trajectory."""

    trajectory_id: str
    run_id: str
    metric_results: tuple[MetricResult, ...] = ()
    overall_score: float = 0.0
    passed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def metric_scores(self) -> dict[str, float]:
        return {r.metric_name: r.normalized_score for r in self.metric_results if r.is_success}

    @property
    def failed_metrics(self) -> tuple[MetricResult, ...]:
        return tuple(r for r in self.metric_results if not r.is_success)


class TrajectoryEvaluator:
    """Evaluates agent trajectories using pluggable metrics.

    Wraps the MetricEngine to provide a trajectory-specific evaluation
    interface. Registers trajectory-specific metrics and evaluates
    them against trajectory data.
    """

    def __init__(
        self,
        metric_engine: MetricEngine | None = None,
        *,
        include_standard_metrics: bool = True,
    ) -> None:
        self._engine = metric_engine or MetricEngine()
        self._initialized = False
        self._include_standard = include_standard_metrics

    async def initialize(self) -> None:
        """Initialize the evaluator by registering trajectory metrics."""
        if self._initialized:
            return

        metrics = [
            TrajectoryCompletenessMetric(),
            TrajectoryEfficiencyMetric(),
            TrajectoryErrorRecoveryMetric(),
            TrajectoryToolSelectionMetric(),
        ]

        for metric in metrics:
            if not self._engine.has_metric(metric.definition().name):
                self._engine.register(metric)

        self._initialized = True

    async def evaluate_trajectory(
        self,
        trajectory: dict[str, Any],
        *,
        prompt: str = "",
        reference: str = "",
        available_tools: tuple[str, ...] = (),
        metric_names: tuple[str, ...] = TRAJECTORY_METRIC_NAMES,
    ) -> TrajectoryEvaluationResult:
        """Evaluate a single trajectory.

        Args:
            trajectory: Serialized trajectory dict (from AgentTrajectory.to_dict()).
            prompt: The original task prompt.
            reference: Expected reference answer.
            available_tools: Available tool names for tool selection validation.
            metric_names: Which trajectory metrics to evaluate.

        Returns:
            TrajectoryEvaluationResult with per-metric scores.
        """
        if not self._initialized:
            await self.initialize()

        trajectory_id = trajectory.get("trajectory_id", "")
        run_id = trajectory.get("run_id", "")

        metadata: dict[str, Any] = {
            "trajectory": trajectory,
            "available_tools": list(available_tools),
        }

        raw_history = trajectory.get("conversation_history", ())
        if isinstance(raw_history, (list, tuple)):
            response_text = "\n".join(
                f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}"
                for msg in raw_history
                if isinstance(msg, dict)
            )
        else:
            response_text = str(raw_history)

        input_data = MetricInput(
            prompt=prompt,
            response=response_text,
            reference=reference,
            metadata=metadata,
        )

        resolved = self._engine.resolve_metrics(metric_names)
        results = await self._engine.evaluate_batch(resolved, input_data)

        successful = [r for r in results if r.is_success]
        if successful:
            overall = sum(r.normalized_score for r in successful) / len(successful)
        else:
            overall = 0.0

        thresholds = {
            m.definition().name: (m.definition().default_threshold or 0.0)
            for m in [
                TrajectoryCompletenessMetric(),
                TrajectoryEfficiencyMetric(),
                TrajectoryErrorRecoveryMetric(),
                TrajectoryToolSelectionMetric(),
            ]
        }

        passed = all(
            r.normalized_score >= thresholds.get(r.metric_name, 0.0)
            for r in results
            if r.is_success and r.metric_name in thresholds
        )

        return TrajectoryEvaluationResult(
            trajectory_id=trajectory_id,
            run_id=run_id,
            metric_results=tuple(results),
            overall_score=overall,
            passed=passed,
            metadata={
                "metric_count": len(results),
                "success_count": len(successful),
            },
        )

    async def evaluate_trajectory_object(
        self,
        trajectory: Any,
        *,
        prompt: str = "",
        reference: str = "",
        available_tools: tuple[str, ...] = (),
        metric_names: tuple[str, ...] = TRAJECTORY_METRIC_NAMES,
    ) -> TrajectoryEvaluationResult:
        """Evaluate an AgentTrajectory object directly."""
        trajectory_dict = trajectory.to_dict() if hasattr(trajectory, "to_dict") else trajectory

        return await self.evaluate_trajectory(
            trajectory_dict,
            prompt=prompt,
            reference=reference,
            available_tools=available_tools,
            metric_names=metric_names,
        )

    def get_available_metrics(self) -> tuple[str, ...]:
        """Return names of available trajectory metrics."""
        return tuple(name for name in TRAJECTORY_METRIC_NAMES if self._engine.has_metric(name))
