"""Base class for LLM judge-backed metrics."""

from __future__ import annotations

import time
from typing import Any

from app.evaluation.judge.domain import JudgeConfig, JudgeRequest
from app.evaluation.metrics.domain import (
    Metric,
    MetricInput,
    MetricResult,
)


class LLMJudgeMetric(Metric):
    """Base class for metrics that use LLM-as-judge.

    Subclasses define the metric name, category, and rubric.
    The base class handles provider resolution, prompt building,
    and JudgeResponse → MetricResult mapping.
    """

    _judge_config: JudgeConfig | None = None

    def set_judge_config(self, config: JudgeConfig) -> None:
        """Set the judge configuration for this metric."""
        self._judge_config = config

    def _get_provider(self, input_data: MetricInput) -> Any:
        """Resolve the chat provider from input metadata."""
        provider = input_data.metadata.get("_judge_provider")
        if provider is None:
            msg = (
                f"Metric '{self.definition().name}' requires a '_judge_provider' "
                "in input metadata. Provide a ChatProvider instance."
            )
            raise RuntimeError(msg)
        return provider

    def _get_judge_config(self, input_data: MetricInput) -> JudgeConfig:
        """Resolve the judge config."""
        return self._judge_config or JudgeConfig(
            provider_name=str(input_data.metadata.get("_judge_provider_name", "")),
            model=str(input_data.metadata.get("_judge_model", "")),
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate using LLM judge."""
        start = time.monotonic()
        metric_def = self.definition()

        if not input_data.response:
            return MetricResult(
                metric_name=metric_def.name,
                score=0.0,
                normalized_score=0.0,
                error="Missing response",
                version=metric_def.version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        validation_error = self.validate_input(input_data)
        if validation_error:
            return MetricResult(
                metric_name=metric_def.name,
                score=0.0,
                normalized_score=0.0,
                error=validation_error,
                version=metric_def.version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            provider = self._get_provider(input_data)
            config = self._get_judge_config(input_data)
        except RuntimeError as exc:
            return MetricResult(
                metric_name=metric_def.name,
                score=0.0,
                normalized_score=0.0,
                error=str(exc),
                version=metric_def.version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
            )

        from app.evaluation.judge.engine import JudgeEngine

        engine = JudgeEngine(default_provider=provider, default_config=config)

        request = JudgeRequest(
            metric_name=metric_def.name,
            prompt=input_data.prompt,
            response=input_data.response,
            context=input_data.context,
            reference=input_data.reference,
            config=config,
        )

        judge_response = await engine.judge(request, provider=provider, config=config)

        if judge_response.error is not None:
            return MetricResult(
                metric_name=metric_def.name,
                score=0.0,
                normalized_score=0.0,
                raw_output=judge_response.raw_output,
                reasoning=judge_response.reasoning,
                metadata={
                    "rubric_version": judge_response.rubric_version,
                    "judge_model": judge_response.judge_model,
                    "judge_prompt_version": judge_response.judge_prompt_version,
                    "tokens_input": judge_response.tokens_input,
                    "tokens_output": judge_response.tokens_output,
                },
                version=metric_def.version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=judge_response.error,
            )

        return MetricResult(
            metric_name=metric_def.name,
            score=judge_response.score,
            normalized_score=max(0.0, min(1.0, judge_response.score)),
            raw_output=judge_response.raw_output,
            reasoning=judge_response.reasoning,
            metadata={
                "rubric_version": judge_response.rubric_version,
                "judge_model": judge_response.judge_model,
                "judge_prompt_version": judge_response.judge_prompt_version,
                "tokens_input": judge_response.tokens_input,
                "tokens_output": judge_response.tokens_output,
            },
            confidence=judge_response.confidence,
            version=metric_def.version,
            cost_usd=judge_response.cost_usd,
            execution_time_ms=int((time.monotonic() - start) * 1000),
        )
