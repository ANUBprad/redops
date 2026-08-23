"""Tool call correctness metric - validates tool call structure."""

from __future__ import annotations

import time

from app.evaluation.metrics.domain import (
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)


class ToolCallCorrectnessMetric(Metric):
    """Evaluates correctness of tool calls in the response.

    Validates that tool calls have required fields (name, arguments)
    and that arguments are well-formed.
    """

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="tool_call_correctness",
            display_name="Tool Call Correctness",
            description="Validates structure and arguments of tool calls",
            category=MetricCategory.VALIDATION,
            scale=MetricScale.CONTINUOUS,
            tags=("validation", "tool_use"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate tool call correctness."""
        start = time.monotonic()

        tool_calls = input_data.tool_calls

        if not tool_calls:
            return MetricResult(
                metric_name="tool_call_correctness",
                score=0.0,
                normalized_score=0.0,
                reasoning="No tool_calls provided in input",
                metadata={"tool_call_count": 0},
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error="No tool_calls provided in input",
            )

        valid_count = 0
        errors: list[str] = []

        for idx, call in enumerate(tool_calls):
            if not isinstance(call, dict):
                errors.append(f"Tool call {idx}: not a dict")
                continue

            name = call.get("name")
            if not name or not isinstance(name, str):
                errors.append(f"Tool call {idx}: missing or invalid 'name'")
                continue

            arguments = call.get("arguments")
            if arguments is None:
                errors.append(f"Tool call {idx}: missing 'arguments'")
                continue

            if isinstance(arguments, str):
                try:
                    import json

                    arguments = json.loads(arguments)
                except (json.JSONDecodeError, ValueError):
                    errors.append(f"Tool call {idx}: invalid JSON arguments")
                    continue

            if not isinstance(arguments, dict):
                errors.append(f"Tool call {idx}: arguments must be a dict")
                continue

            valid_count += 1

        score = valid_count / len(tool_calls) if tool_calls else 1.0

        return MetricResult(
            metric_name="tool_call_correctness",
            score=float(valid_count),
            normalized_score=max(0.0, min(score, 1.0)),
            reasoning=f"{valid_count}/{len(tool_calls)} tool calls are valid",
            metadata={
                "valid_calls": valid_count,
                "total_calls": len(tool_calls),
                "errors": errors,
            },
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
