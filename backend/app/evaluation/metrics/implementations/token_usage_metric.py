"""Token usage metric - measures token efficiency."""

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


class TokenUsageMetric(Metric):
    """Evaluates token usage efficiency.

    Scores based on output token count relative to a configurable limit.
    Lower token usage for equivalent quality scores higher.
    """

    DEFAULT_MAX_TOKENS = 4096

    def definition(self) -> MetricDefinition:
        """Return the metric definition."""
        return MetricDefinition(
            name="token_usage",
            display_name="Token Usage",
            description="Measures token usage efficiency",
            category=MetricCategory.COST,
            scale=MetricScale.CONTINUOUS,
            tags=("cost", "efficiency"),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate token usage from metadata."""
        start = time.monotonic()

        if "tokens_output" not in input_data.metadata:
            return MetricResult(
                metric_name="token_usage",
                score=0.0,
                normalized_score=0.0,
                reasoning="tokens_output not provided in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error="tokens_output not provided in metadata",
            )

        tokens_output = input_data.metadata.get("tokens_output", 0)
        if not isinstance(tokens_output, (int, float)):
            return MetricResult(
                metric_name="token_usage",
                score=0.0,
                normalized_score=0.0,
                error="Invalid tokens_output in metadata",
                version=self.definition().version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        max_tokens = self.DEFAULT_MAX_TOKENS

        score = 1.0 if tokens_output <= 0 else max(0.0, 1.0 - (tokens_output / max_tokens))

        return MetricResult(
            metric_name="token_usage",
            score=float(tokens_output),
            normalized_score=max(0.0, min(score, 1.0)),
            reasoning=f"Used {tokens_output}/{max_tokens} tokens",
            metadata={"tokens_output": tokens_output, "max_tokens": max_tokens},
            version=self.definition().version,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
