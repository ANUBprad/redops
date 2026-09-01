"""Semantic effectiveness metric — LLM judge-backed evaluation.

Exposes red-team semantic effectiveness as a first-class metric in the
general evaluation engine. It reuses the red-team semantic judge (a real
LLM judgment of whether an attack objective was achieved) and maps its
result into the canonical ``MetricResult`` so it can be aggregated,
persisted, and reported through the general metrics pipeline.

The attack objective is taken from ``input_data.context`` (the scenario's
expected behavior), the attack prompt is ``input_data.prompt``, and the
target model's response is ``input_data.response``.
"""

from __future__ import annotations

import time
from typing import Any

from app.evaluation.judge.domain import JudgeConfig
from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)


class SemanticEffectivenessMetric(Metric):
    """Evaluates how effectively a prompt achieved its intended objective.

    This is the general-engine representation of the red-team semantic
    effectiveness judgment. It performs a real LLM judge call (via the
    red-team ``SemanticEffectivenessJudge``) and emits a canonical
    ``MetricResult`` whose score is the semantic effectiveness score.
    """

    _judge_config: JudgeConfig | None = None

    def set_judge_config(self, config: JudgeConfig) -> None:
        """Set the judge configuration for this metric."""
        self._judge_config = config

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="semantic_effectiveness",
            display_name="Semantic Effectiveness",
            description=(
                "Determines, via an LLM judge, whether an attack prompt's "
                "objective was semantically achieved by the target response "
                "rather than relying on keyword matching"
            ),
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            tags=("quality", "red_team", "llm_judge"),
            evaluator_type=EvaluatorType.LLM_JUDGE,
            required_inputs=("prompt", "response", "context"),
        )

    def _get_provider(self, input_data: MetricInput) -> Any:
        """Resolve the chat provider from input metadata."""
        provider = input_data.metadata.get("_judge_provider")
        if provider is None:
            msg = (
                "Metric 'semantic_effectiveness' requires a '_judge_provider' "
                "in input metadata. Provide a ChatProvider instance."
            )
            raise RuntimeError(msg)
        return provider

    def _get_judge_config(self, input_data: MetricInput) -> JudgeConfig:
        """Resolve the judge config from input metadata."""
        return self._judge_config or JudgeConfig(
            provider_name=str(input_data.metadata.get("_judge_provider_name") or ""),
            model=str(input_data.metadata.get("_judge_model") or ""),
            temperature=0.0,
            max_tokens=512,
        )

    def _resolve_provider_name(self, input_data: MetricInput, provider: Any) -> str:
        """Record which provider executed the judge call."""
        configured = input_data.metadata.get("_judge_provider_name")
        if configured:
            return str(configured)
        return str(getattr(provider, "provider_name", ""))

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        """Evaluate semantic effectiveness using a real LLM judge call."""
        start = time.monotonic()
        metric_def = self.definition()

        missing = [f for f in ("prompt", "response") if not getattr(input_data, f)]
        if missing:
            return MetricResult(
                metric_name=metric_def.name,
                score=0.0,
                normalized_score=0.0,
                error=f"Missing input: {', '.join(missing)}",
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

        from app.redteam.engine.semantic_judge import SemanticEffectivenessJudge

        judge = SemanticEffectivenessJudge(provider=provider, config=config)

        objective = input_data.context or ""
        if not objective:
            category = str(input_data.metadata.get("category") or "harmful")
            objective = (
                f"The attack aims to cause the target model to exhibit {category} behavior"
            )

        try:
            verdict = await judge.evaluate(
                attack_prompt=input_data.prompt,
                attack_objective=objective,
                target_response=input_data.response,
                metadata=input_data.metadata,
            )
        except Exception as exc:
            return MetricResult(
                metric_name=metric_def.name,
                score=0.0,
                normalized_score=0.0,
                raw_output="",
                reasoning=f"Semantic judge execution failed: {exc}",
                version=metric_def.version,
                execution_time_ms=int((time.monotonic() - start) * 1000),
                error=str(exc),
            )

        error = verdict.error
        score = verdict.score if not verdict.has_error else 0.0

        return MetricResult(
            metric_name=metric_def.name,
            score=score,
            normalized_score=max(0.0, min(1.0, score)),
            raw_output="",
            reasoning=verdict.reasoning,
            metadata={
                "verdict": verdict.verdict,
                "evidence": verdict.evidence,
                "judge_model": verdict.judge_model,
                "judge_cost_usd": verdict.judge_cost_usd,
                "tokens_input": verdict.judge_tokens_input,
                "tokens_output": verdict.judge_tokens_output,
                "judge_latency_ms": verdict.judge_latency_ms,
                "provider": self._resolve_provider_name(input_data, provider),
            },
            confidence=verdict.confidence,
            version=metric_def.version,
            cost_usd=verdict.judge_cost_usd,
            execution_time_ms=int((time.monotonic() - start) * 1000),
            error=error,
        )
