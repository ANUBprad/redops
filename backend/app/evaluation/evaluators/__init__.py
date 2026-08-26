"""Evaluator abstraction layer.

Provides adapter pattern for different evaluation backends.
"""

from app.evaluation.evaluators.adapters import (
    CustomAdapter,
    EmbeddingAdapter,
    HeuristicAdapter,
    LLMJudgeAdapter,
    RAGASAdapter,
)
from app.evaluation.evaluators.base import (
    BaseEvaluatorAdapter,
    EvaluatorConfig,
    EvaluatorRegistry,
)

__all__ = [
    "BaseEvaluatorAdapter",
    "CustomAdapter",
    "EmbeddingAdapter",
    "EvaluatorConfig",
    "EvaluatorRegistry",
    "HeuristicAdapter",
    "LLMJudgeAdapter",
    "RAGASAdapter",
]
