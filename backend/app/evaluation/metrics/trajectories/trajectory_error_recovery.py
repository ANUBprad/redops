"""Trajectory error recovery metric — evaluates how well the agent handles errors.

Measures whether the agent can recover from tool execution failures
by trying alternative approaches or retrying with corrected arguments.
"""

from __future__ import annotations

import time

from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
    ScoreDirection,
)


class TrajectoryErrorRecoveryMetric(Metric):
    """Evaluates error recovery capability in agent trajectories.

    A good error recovery score means:
    - When a tool call fails, the agent attempts a different approach
    - The agent does not get stuck in retry loops
    - The agent can still produce a valid response despite errors

    Score: 1.0 = excellent recovery, 0.0 = no recovery attempted
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="trajectory_error_recovery",
            display_name="Trajectory Error Recovery",
            description="Evaluates how well the agent recovers from tool execution errors",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            default_threshold=0.3,
            tags=("trajectory", "agent", "deterministic", "robustness"),
            evaluator_type=EvaluatorType.HEURISTIC,
            required_inputs=("response",),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        trajectory = input_data.metadata.get("trajectory")
        if trajectory is None:
            return MetricResult(
                metric_name="trajectory_error_recovery",
                score=0.0,
                normalized_score=0.0,
                reasoning="No trajectory provided in metadata",
                error="No trajectory provided in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        steps = trajectory.get("steps", [])
        metrics = trajectory.get("metrics", {})
        total_errors = metrics.get("errors", 0)
        tool_calls = metrics.get("tool_calls", 0)

        if total_errors == 0 and tool_calls == 0:
            return MetricResult(
                metric_name="trajectory_error_recovery",
                score=1.0,
                normalized_score=1.0,
                reasoning="No errors encountered; recovery not applicable",
                metadata={"error_count": 0, "tool_call_count": 0},
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        if total_errors == 0:
            return MetricResult(
                metric_name="trajectory_error_recovery",
                score=1.0,
                normalized_score=1.0,
                reasoning="No errors encountered during execution",
                metadata={"error_count": 0},
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        error_steps: list[int] = []
        post_error_steps = 0
        recovery_attempts = 0

        for i, step in enumerate(steps):
            if step.get("step_type") == "error" or (
                step.get("tool_call") and step.get("tool_call", {}).get("is_error")
            ):
                error_steps.append(i)

        for error_idx in error_steps:
            subsequent = steps[error_idx + 1 :]
            for next_step in subsequent:
                if next_step.get("step_type") in (
                    "llm_call",
                    "tool_call",
                    "final_answer",
                ):
                    post_error_steps += 1
                    if next_step.get("step_type") == "tool_call":
                        recovery_attempts += 1
                    break

        recovered_count = 0
        for error_idx in error_steps:
            subsequent = steps[error_idx + 1 :]
            for next_step in subsequent:
                if next_step.get("step_type") == "final_answer":
                    recovered_count += 1
                    break
                if next_step.get("step_type") == "error":
                    break

        score = 0.0
        reasoning_parts: list[str] = []

        recovery_rate = recovered_count / total_errors if total_errors > 0 else 0.0
        score += recovery_rate * 0.5
        reasoning_parts.append(f"recovered from {recovered_count}/{total_errors} errors")

        if post_error_steps > 0:
            score += 0.3
            reasoning_parts.append(f"continued execution after {post_error_steps} errors")
        else:
            reasoning_parts.append("did not continue after errors")

        if recovery_attempts > 0:
            score += 0.2
            reasoning_parts.append(f"made {recovery_attempts} recovery attempts")
        else:
            reasoning_parts.append("no alternative approaches attempted")

        return MetricResult(
            metric_name="trajectory_error_recovery",
            score=score,
            normalized_score=max(0.0, min(score, 1.0)),
            reasoning="; ".join(reasoning_parts),
            metadata={
                "error_count": total_errors,
                "recovered_count": recovered_count,
                "recovery_rate": recovery_rate,
                "post_error_steps": post_error_steps,
                "recovery_attempts": recovery_attempts,
            },
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
