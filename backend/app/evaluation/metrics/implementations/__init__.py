"""Built-in metric implementations.

Each metric is independently executable and follows the Metric ABC.
"""

from app.evaluation.metrics.implementations.answer_relevance_metric import (
    AnswerRelevanceMetric,
)
from app.evaluation.metrics.implementations.bias_metric import BiasMetric
from app.evaluation.metrics.implementations.coherence_metric import CoherenceMetric
from app.evaluation.metrics.implementations.context_relevance_metric import (
    ContextRelevanceMetric,
)
from app.evaluation.metrics.implementations.correctness_metric import CorrectnessMetric
from app.evaluation.metrics.implementations.cost_metric import CostMetric
from app.evaluation.metrics.implementations.faithfulness_metric import FaithfulnessMetric
from app.evaluation.metrics.implementations.groundedness_metric import GroundednessMetric
from app.evaluation.metrics.implementations.hallucination_metric import HallucinationMetric
from app.evaluation.metrics.implementations.instruction_following_metric import (
    InstructionFollowingMetric,
)
from app.evaluation.metrics.implementations.jailbreak_metric import JailbreakMetric
from app.evaluation.metrics.implementations.json_validity_metric import JsonValidityMetric
from app.evaluation.metrics.implementations.latency_metric import LatencyMetric
from app.evaluation.metrics.implementations.prompt_injection_metric import (
    PromptInjectionMetric,
)
from app.evaluation.metrics.implementations.reasoning_quality_metric import (
    ReasoningQualityMetric,
)
from app.evaluation.metrics.implementations.regex_validation_metric import (
    RegexValidationMetric,
)
from app.evaluation.metrics.implementations.response_length_metric import (
    ResponseLengthMetric,
)
from app.evaluation.metrics.implementations.safety_metric import SafetyMetric
from app.evaluation.metrics.implementations.schema_validation_metric import (
    SchemaValidationMetric,
)
from app.evaluation.metrics.implementations.semantic_similarity_metric import (
    SemanticSimilarityMetric,
)
from app.evaluation.metrics.implementations.token_usage_metric import TokenUsageMetric
from app.evaluation.metrics.implementations.tool_call_correctness_metric import (
    ToolCallCorrectnessMetric,
)
from app.evaluation.metrics.implementations.toxicity_metric import ToxicityMetric

ALL_METRICS: list[type] = [
    # Tier 1 — Deterministic
    CostMetric,
    LatencyMetric,
    TokenUsageMetric,
    JsonValidityMetric,
    SchemaValidationMetric,
    ResponseLengthMetric,
    RegexValidationMetric,
    ToolCallCorrectnessMetric,
    GroundednessMetric,
    # Tier 2 — Embedding
    SemanticSimilarityMetric,
    AnswerRelevanceMetric,
    ContextRelevanceMetric,
    # Tier 3 — LLM Judge
    CorrectnessMetric,
    FaithfulnessMetric,
    HallucinationMetric,
    InstructionFollowingMetric,
    ReasoningQualityMetric,
    CoherenceMetric,
    SafetyMetric,
    BiasMetric,
    ToxicityMetric,
    PromptInjectionMetric,
    JailbreakMetric,
]

__all__ = [
    "ALL_METRICS",
    "AnswerRelevanceMetric",
    "BiasMetric",
    "CoherenceMetric",
    "ContextRelevanceMetric",
    "CorrectnessMetric",
    "CostMetric",
    "FaithfulnessMetric",
    "GroundednessMetric",
    "HallucinationMetric",
    "InstructionFollowingMetric",
    "JailbreakMetric",
    "JsonValidityMetric",
    "LatencyMetric",
    "PromptInjectionMetric",
    "ReasoningQualityMetric",
    "RegexValidationMetric",
    "ResponseLengthMetric",
    "SafetyMetric",
    "SchemaValidationMetric",
    "SemanticSimilarityMetric",
    "TokenUsageMetric",
    "ToolCallCorrectnessMetric",
    "ToxicityMetric",
]
