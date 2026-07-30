"""Built-in metric implementations.

Each metric is independently executable and follows the Metric ABC.
"""

from app.evaluation.metrics.implementations.correctness_metric import CorrectnessMetric
from app.evaluation.metrics.implementations.cost_metric import CostMetric
from app.evaluation.metrics.implementations.faithfulness_metric import FaithfulnessMetric
from app.evaluation.metrics.implementations.groundedness_metric import GroundednessMetric
from app.evaluation.metrics.implementations.hallucination_metric import HallucinationMetric
from app.evaluation.metrics.implementations.json_validity_metric import JsonValidityMetric
from app.evaluation.metrics.implementations.latency_metric import LatencyMetric
from app.evaluation.metrics.implementations.relevance_metric import RelevanceMetric
from app.evaluation.metrics.implementations.token_usage_metric import TokenUsageMetric
from app.evaluation.metrics.implementations.tool_call_correctness_metric import (
    ToolCallCorrectnessMetric,
)

ALL_METRICS: list[type] = [
    CorrectnessMetric,
    CostMetric,
    FaithfulnessMetric,
    GroundednessMetric,
    HallucinationMetric,
    JsonValidityMetric,
    LatencyMetric,
    RelevanceMetric,
    TokenUsageMetric,
    ToolCallCorrectnessMetric,
]

__all__ = [
    "ALL_METRICS",
    "CorrectnessMetric",
    "CostMetric",
    "FaithfulnessMetric",
    "GroundednessMetric",
    "HallucinationMetric",
    "JsonValidityMetric",
    "LatencyMetric",
    "RelevanceMetric",
    "TokenUsageMetric",
    "ToolCallCorrectnessMetric",
]
