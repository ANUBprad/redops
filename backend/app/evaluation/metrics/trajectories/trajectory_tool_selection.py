"""Trajectory tool selection metric — evaluates whether the agent chose the right tools.

Compares the tools used against the available tool registry and
checks if the tool selection was appropriate for the task.
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


class TrajectoryToolSelectionMetric(Metric):
    """Evaluates the quality of tool selection in an agent trajectory.

    Assesses:
    - Whether the agent used tools that are available in the registry
    - Whether the agent avoided calling non-existent tools
    - Whether the tool usage pattern makes sense (not just one tool repeated)

    Score: 1.0 = optimal tool selection, 0.0 = completely wrong tools
    """

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="trajectory_tool_selection",
            display_name="Trajectory Tool Selection",
            description="Evaluates whether the agent selected appropriate tools for the task",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            default_threshold=0.5,
            tags=("trajectory", "agent", "deterministic", "tool_use"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        start = time.monotonic()

        trajectory = input_data.metadata.get("trajectory")
        if trajectory is None:
            return MetricResult(
                metric_name="trajectory_tool_selection",
                score=0.0,
                normalized_score=0.0,
                reasoning="No trajectory provided in metadata",
                error="No trajectory provided in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        available_tools = input_data.metadata.get("available_tools", [])
        steps = trajectory.get("steps", [])
        metrics_data = trajectory.get("metrics", {})
        tools_used = list(metrics_data.get("unique_tools_used", []))

        tool_calls = [
            s for s in steps if s.get("step_type") == "tool_call"
        ]

        if not tool_calls and not tools_used:
            return MetricResult(
                metric_name="trajectory_tool_selection",
                score=0.5,
                normalized_score=0.5,
                reasoning="No tools used in trajectory (may be valid for text-only tasks)",
                metadata={
                    "tools_used": [],
                    "available_tools": list(available_tools),
                },
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        score = 0.0
        reasoning_parts: list[str] = []

        if available_tools:
            valid_tools = [t for t in tools_used if t in available_tools]
            invalid_tools = [t for t in tools_used if t not in available_tools]

            if tools_used:
                validity_rate = len(valid_tools) / len(tools_used)
                score += validity_rate * 0.5
                if invalid_tools:
                    reasoning_parts.append(
                        f"invalid tools called: {invalid_tools}"
                    )
                else:
                    reasoning_parts.append("all tools are valid")
        else:
            score += 0.3
            reasoning_parts.append("no tool registry provided for validation")

        if len(tools_used) > 1:
            score += 0.3
            reasoning_parts.append(
                f"used {len(tools_used)} different tools (good diversity)"
            )
        elif len(tools_used) == 1:
            score += 0.15
            reasoning_parts.append("used only 1 tool (may be appropriate)")

        tool_call_counts: dict[str, int] = {}
        for s in tool_calls:
            tc = s.get("tool_call", {})
            name = tc.get("tool_name", "")
            if name:
                tool_call_counts[name] = tool_call_counts.get(name, 0) + 1

        max_repeats = max(tool_call_counts.values()) if tool_call_counts else 0
        if max_repeats <= 3:
            score += 0.2
            reasoning_parts.append("no excessive tool repetition")
        elif max_repeats <= 5:
            score += 0.1
            reasoning_parts.append(f"tool repeated {max_repeats} times")
        else:
            reasoning_parts.append(
                f"excessive tool repetition ({max_repeats} times)"
            )

        return MetricResult(
            metric_name="trajectory_tool_selection",
            score=score,
            normalized_score=max(0.0, min(score, 1.0)),
            reasoning="; ".join(reasoning_parts),
            metadata={
                "tools_used": tools_used,
                "available_tools": list(available_tools),
                "tool_call_counts": tool_call_counts,
                "max_repeats": max_repeats,
            },
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
