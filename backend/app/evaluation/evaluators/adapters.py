"""Built-in evaluator adapters.

Provides concrete implementations of BaseEvaluatorAdapter for
heuristic, embedding, LLM judge, and custom evaluation backends.
"""

from __future__ import annotations

from typing import Any

from app.evaluation.evaluators.base import (
    BaseEvaluatorAdapter,
    EvaluatorConfig,
)
from app.evaluation.metrics.domain import (
    EvaluatorType,
    MetricInput,
    MetricResult,
)


class HeuristicAdapter(BaseEvaluatorAdapter):
    """Adapter for deterministic, code-only metric evaluation.

    This is the default adapter for metrics that compute scores
    purely from input data without any external API calls.
    """

    def evaluator_type(self) -> EvaluatorType:
        return EvaluatorType.HEURISTIC

    async def evaluate(
        self,
        metric_name: str,
        input_data: MetricInput,
        config: EvaluatorConfig | None = None,
    ) -> MetricResult:
        msg = (
            f"HeuristicAdapter cannot directly evaluate '{metric_name}'. "
            "Use the Metric instance's evaluate() method instead."
        )
        raise NotImplementedError(msg)


class EmbeddingAdapter(BaseEvaluatorAdapter):
    """Adapter for embedding-based metric evaluation.

    Wraps provider embedding models for cosine similarity and
    related embedding computations.
    """

    def evaluator_type(self) -> EvaluatorType:
        return EvaluatorType.EMBEDDING

    async def evaluate(
        self,
        metric_name: str,
        input_data: MetricInput,
        config: EvaluatorConfig | None = None,
    ) -> MetricResult:
        msg = (
            f"EmbeddingAdapter cannot directly evaluate '{metric_name}'. "
            "Use the Metric instance's evaluate() method instead."
        )
        raise NotImplementedError(msg)


class LLMJudgeAdapter(BaseEvaluatorAdapter):
    """Adapter for LLM-as-judge metric evaluation.

    Delegates to the JudgeEngine for prompt-based evaluation.
    """

    def evaluator_type(self) -> EvaluatorType:
        return EvaluatorType.LLM_JUDGE

    async def evaluate(
        self,
        metric_name: str,
        input_data: MetricInput,
        config: EvaluatorConfig | None = None,
    ) -> MetricResult:
        msg = (
            f"LLMJudgeAdapter cannot directly evaluate '{metric_name}'. "
            "Use the Metric instance's evaluate() method instead."
        )
        raise NotImplementedError(msg)


class RAGASAdapter(BaseEvaluatorAdapter):
    """Adapter for RAGAS framework evaluation.

    Delegates to the RAGAS library for RAG-specific metrics
    (faithfulness, answer relevancy, context precision, etc.).

    Requires ``ragas`` to be installed:
        pip install ragas

    When RAGAS is not installed, evaluation raises ImportError.
    """

    def evaluator_type(self) -> EvaluatorType:
        return EvaluatorType.RAGAS

    async def evaluate(
        self,
        metric_name: str,
        input_data: MetricInput,
        config: EvaluatorConfig | None = None,
    ) -> MetricResult:
        try:
            return await self._evaluate_with_ragas(metric_name, input_data, config)
        except ImportError:
            return MetricResult(
                metric_name=metric_name,
                score=0.0,
                normalized_score=0.0,
                error="ragas package not installed. Install with: pip install ragas",
            )

    async def _evaluate_with_ragas(
        self,
        metric_name: str,
        input_data: MetricInput,
        config: EvaluatorConfig | None = None,
    ) -> MetricResult:
        """Evaluate using the RAGAS framework."""
        import ragas  # type: ignore[import-not-found]
        from ragas import metrics as ragas_metrics  # type: ignore[import-not-found]

        ragas_metric_map = {
            "faithfulness": ragas_metrics.Faithfulness(),
            "answer_relevancy": ragas_metrics.AnswerRelevancy(),
            "context_precision": ragas_metrics.ContextPrecision(),
            "context_recall": ragas_metrics.ContextRecall(),
        }

        ragas_metric = ragas_metric_map.get(metric_name)
        if ragas_metric is None:
            return MetricResult(
                metric_name=metric_name,
                score=0.0,
                normalized_score=0.0,
                error=f"RAGAS does not support metric '{metric_name}'. "
                f"Supported: {list(ragas_metric_map.keys())}",
            )

        from ragas import EvaluationDataset, SingleTurnSample  # type: ignore[import-not-found]

        sample = SingleTurnSample(
            user_input=input_data.prompt,
            response=input_data.response,
            retrieved_contexts=[input_data.context] if input_data.context else [],
            reference=input_data.reference if input_data.reference else "",
        )
        dataset = EvaluationDataset(samples=[sample])

        result = ragas.evaluate(dataset, metrics=[ragas_metric])
        score = result.score  # type: ignore[union-attr]

        return MetricResult(
            metric_name=metric_name,
            score=float(score),
            normalized_score=min(max(float(score), 0.0), 1.0),
            reasoning=f"RAGAS {metric_name} evaluation",
        )


class CustomAdapter(BaseEvaluatorAdapter):
    """Adapter for user-defined or plugin-provided evaluation.

    Allows external plugins to register their own evaluation logic
    via the entry_points system.
    """

    def __init__(self) -> None:
        """Initialize with an empty custom evaluator map."""
        self._custom_evaluators: dict[str, Any] = {}

    def evaluator_type(self) -> EvaluatorType:
        return EvaluatorType.CUSTOM

    def register_evaluator(
        self,
        metric_name: str,
        evaluator_fn: Any,
    ) -> None:
        """Register a custom evaluator function for a metric."""
        self._custom_evaluators[metric_name] = evaluator_fn

    async def evaluate(
        self,
        metric_name: str,
        input_data: MetricInput,
        config: EvaluatorConfig | None = None,
    ) -> MetricResult:
        evaluator_fn = self._custom_evaluators.get(metric_name)
        if evaluator_fn is None:
            return MetricResult(
                metric_name=metric_name,
                score=0.0,
                normalized_score=0.0,
                error=f"No custom evaluator registered for '{metric_name}'",
            )
        try:
            result = await evaluator_fn(input_data, config)
            return result
        except Exception as e:
            return MetricResult(
                metric_name=metric_name,
                score=0.0,
                normalized_score=0.0,
                error=f"Custom evaluator failed: {e}",
            )
