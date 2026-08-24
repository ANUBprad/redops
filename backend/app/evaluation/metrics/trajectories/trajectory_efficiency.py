"""Trajectory efficiency metric — measures how efficiently the agent completed the task.

Evaluates the ratio of useful steps (tool calls that succeeded) to
total steps, and penalizes excessive LLM calls or redundant tool invocations.
"""

from __future__ import annotations

import time

from app.evaluation.metrics.domain import (
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
    ScoreDirection,
)


class TrajectoryEfficiencyMetric(Metric):
    """Evaluates the efficiency of an agent trajectory.

    Considers:
    - Steps per tool call ratio (lower is better, up to a point)
    - Tool error rate (lower is better)
    - Whether the agent converged without unnecessary loops

    Score: 1.0 = perfectly efficient, 0.0 = extremely wasteful
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="trajectory_efficiency",
            display_name="Trajectory Efficiency",
            description="Measures how efficiently the agent completed the task",
            category=MetricCategory.PERFORMANCE,
            scale=MetricScale.CONTINUOUS,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            default_threshold=0.4,
            tags=("trajectory", "agent", "deterministic", "performance"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        trajectory = input_data.metadata.get("trajectory")
        if trajectory is None:
            return MetricResult(
                metric_name="trajectory_efficiency",
                score=0.0,
                normalized_score=0.0,
                reasoning="No trajectory provided in metadata",
                error="No trajectory provided in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        metrics = trajectory.get("metrics", {})
        total_steps = metrics.get("total_steps", 0)
        tool_calls = metrics.get("tool_calls", 0)
        llm_calls = metrics.get("llm_calls", 0)
        tool_error_rate = metrics.get("tool_error_rate", 0.0)

        if total_steps == 0:
            return MetricResult(
                metric_name="trajectory_efficiency",
                score=0.0,
                normalized_score=0.0,
                reasoning="No steps in trajectory",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        score = 0.0
        reasoning_parts: list[str] = []

        if tool_calls > 0:
            steps_per_tool = total_steps / tool_calls
            if steps_per_tool <= 2.0:
                score += 0.4
                reasoning_parts.append(
                    f"good steps/tool ratio ({steps_per_tool:.1f})"
                )
            elif steps_per_tool <= 4.0:
                score += 0.2
                reasoning_parts.append(
                    f"moderate steps/tool ratio ({steps_per_tool:.1f})"
                )
            else:
                reasoning_parts.append(
                    f"high steps/tool ratio ({steps_per_tool:.1f})"
                )
        else:
            score += 0.3
            reasoning_parts.append("no tool calls (text-only trajectory)")

        error_penalty = tool_error_rate * 0.3
        score += max(0.0, 0.3 - error_penalty)
        if tool_error_rate > 0:
            reasoning_parts.append(
                f"tool error rate {tool_error_rate:.1%}"
            )
        else:
            reasoning_parts.append("no tool errors")

        if llm_calls > 0 and tool_calls > 0:
            convergence = tool_calls / llm_calls
            if convergence >= 0.8:
                score += 0.3
                reasoning_parts.append("good tool utilization per LLM call")
            elif convergence >= 0.5:
                score += 0.15
                reasoning_parts.append("moderate tool utilization")
            else:
                reasoning_parts.append("low tool utilization per LLM call")
        else:
            score += 0.2

        return MetricResult(
            metric_name="trajectory_efficiency",
            score=score,
            normalized_score=max(0.0, min(score, 1.0)),
            reasoning="; ".join(reasoning_parts),
            metadata={
                "total_steps": total_steps,
                "tool_calls": tool_calls,
                "llm_calls": llm_calls,
                "steps_per_tool": total_steps / tool_calls if tool_calls else 0,
                "tool_error_rate": tool_error_rate,
            },
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
