"""Trajectory completeness metric — evaluates if the agent reached the goal.

Deterministic metric that checks whether the trajectory has a final
answer and whether all tool calls succeeded.
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


class TrajectoryCompletenessMetric(Metric):
    """Evaluates whether the agent trajectory reached a complete state.

    A trajectory is complete when:
    1. It has a non-empty final response
    2. The trajectory status is 'completed'
    3. The final step is a FINAL_ANSWER or the last LLM call has no tool calls

    Score: 1.0 = fully complete, 0.0 = not complete
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="trajectory_completeness",
            display_name="Trajectory Completeness",
            description="Evaluates whether the agent reached a complete final answer",
            category=MetricCategory.VALIDATION,
            scale=MetricScale.CONTINUOUS,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            default_threshold=0.5,
            tags=("trajectory", "agent", "deterministic"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        trajectory = input_data.metadata.get("trajectory")
        if trajectory is None:
            return MetricResult(
                metric_name="trajectory_completeness",
                score=0.0,
                normalized_score=0.0,
                reasoning="No trajectory provided in metadata",
                error="No trajectory provided in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        status = trajectory.get("status", "")
        final_response = ""
        steps = trajectory.get("steps", [])

        for step in reversed(steps):
            if step.get("step_type") == "final_answer":
                final_response = step.get("content", "")
                break
            if step.get("step_type") == "llm_call" and not step.get("llm_call", {}).get(
                "tool_calls_requested"
            ):
                final_response = step.get("content", "")
                break

        score = 0.0
        reasoning_parts: list[str] = []

        if status == "completed":
            score += 0.5
            reasoning_parts.append("trajectory status is completed")
        elif status == "max_steps_reached":
            score += 0.2
            reasoning_parts.append("trajectory reached max steps")
        else:
            reasoning_parts.append(f"trajectory status is {status}")

        if final_response and len(final_response.strip()) > 0:
            score += 0.5
            reasoning_parts.append("has non-empty final response")
        else:
            reasoning_parts.append("no final response found")

        return MetricResult(
            metric_name="trajectory_completeness",
            score=score,
            normalized_score=max(0.0, min(score, 1.0)),
            reasoning="; ".join(reasoning_parts),
            metadata={
                "status": status,
                "has_final_response": bool(final_response),
                "final_response_length": len(final_response),
            },
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
