"""Value objects for the Red Team domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.kernel.entities.base import UUIDv7
from app.redteam.domain.enums import AttackCategory, AttackSeverity, SafetyDimension, SafetyVerdict


@dataclass(frozen=True, slots=True)
class AttackTemplate:
    name: str = ""
    description: str = ""
    category: AttackCategory = AttackCategory.PROMPT_INJECTION
    severity: AttackSeverity = AttackSeverity.MEDIUM
    prompt_template: str = ""
    system_prompt_override: str | None = None
    expected_behavior: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class AttackScenario:
    scenario_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    attack_definition_id: UUIDv7 | None = None
    template_name: str = ""
    category: AttackCategory = AttackCategory.PROMPT_INJECTION
    severity: AttackSeverity = AttackSeverity.MEDIUM
    prompt: str = ""
    system_prompt_override: str | None = None
    expected_behavior: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    turn_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SafetyScore:
    dimension: SafetyDimension = SafetyDimension.HARMlessness
    score: float = 0.0
    normalized_score: float = 0.0
    verdict: SafetyVerdict = SafetyVerdict.SAFE
    reasoning: str = ""
    confidence: float = 1.0

    @property
    def is_violation(self) -> bool:
        return self.verdict in (SafetyVerdict.VIOLATED, SafetyVerdict.LEAKED)


@dataclass(frozen=True, slots=True)
class AttackResult:
    scenario: AttackScenario = field(default_factory=AttackScenario)
    response: str = ""
    scores: tuple[SafetyScore, ...] = field(default_factory=tuple)
    execution_time_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    error: str | None = None

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_violation(self) -> bool:
        return any(s.is_violation for s in self.scores)


@dataclass(frozen=True, slots=True)
class AttackMutation:
    mutation_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    name: str = ""
    description: str = ""
    transform: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AttackConfiguration:
    target_provider: str = ""
    target_model: str = ""
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_seconds: int = 60
    system_prompt: str = ""
    attack_definitions: tuple[UUIDv7, ...] = field(default_factory=tuple)
    categories: tuple[AttackCategory, ...] = field(default_factory=tuple)
    severities: tuple[AttackSeverity, ...] = field(default_factory=tuple)
    max_scenarios: int = 0
    mutations: tuple[AttackMutation, ...] = field(default_factory=tuple)
    continue_on_violation: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
