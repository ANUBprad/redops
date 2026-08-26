"""Domain types for the Judge Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RubricEntry:
    """A single rubric criterion for scoring."""

    score: float
    label: str
    description: str


@dataclass(frozen=True, slots=True)
class RubricVersion:
    """Versioned rubric for a specific metric."""

    metric_name: str
    version: str
    entries: tuple[RubricEntry, ...]
    description: str = ""


@dataclass(frozen=True, slots=True)
class JudgeConfig:
    """Configuration for a judge invocation."""

    provider_name: str = ""
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 1024
    rubric_version: str = "1.0.0"
    timeout_seconds: float = 60.0


@dataclass(frozen=True, slots=True)
class JudgeRequest:
    """A request to the judge engine."""

    metric_name: str
    prompt: str
    response: str
    context: str = ""
    reference: str = ""
    rubric: RubricVersion | None = None
    config: JudgeConfig | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JudgeResponse:
    """Structured response from the judge engine.

    ``error`` is set when the judge could not produce a trustworthy
    score (provider failure or malformed output). In that case the
    score fields are placeholders and MUST NOT be consumed.
    """

    score: float
    confidence: float
    reasoning: str
    rubric_version: str
    judge_model: str
    judge_prompt_version: str
    raw_output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: int = 0
    cost_usd: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    error: str | None = None
