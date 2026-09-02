"""Domain model for adaptive red team campaigns.

Defines the campaign aggregate root, rounds, target executions,
budget tracking, attack lineage, and campaign results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.kernel.entities.base import AggregateRoot, UUIDv7, VersionMixin
from app.kernel.exceptions.errors import ConflictError, DomainError
from app.redteam.domain.campaign_enums import CampaignState, MutationPhase
from app.redteam.domain.enums import (
    AttackCategory,
    SafetyVerdict,
)
from app.redteam.domain.events import (
    AttackRunCompleted,
    AttackRunCreated,
    AttackRunFailed,
    AttackRunStarted,
)
from app.redteam.domain.value_objects import AttackScenario, SafetyScore

if TYPE_CHECKING:
    from app.evaluation.metrics.domain import MetricResult


@dataclass(frozen=True, slots=True)
class CampaignBudget:
    """Budget constraints for an adaptive campaign."""

    max_rounds: int = 10
    max_attacks: int = 100
    max_total_tokens: int = 1_000_000
    max_cost_usd: float = 50.0
    max_duration_seconds: int = 3600
    effectiveness_threshold: float = 0.8

    def is_within_limits(
        self,
        *,
        current_round: int,
        total_attacks: int,
        total_tokens: int,
        total_cost: float,
        elapsed_seconds: float,
    ) -> bool:
        """Check if any budget constraint is exceeded."""
        if current_round >= self.max_rounds:
            return False
        if total_attacks >= self.max_attacks:
            return False
        if total_tokens >= self.max_total_tokens:
            return False
        if total_cost >= self.max_cost_usd:
            return False
        return not elapsed_seconds >= self.max_duration_seconds

    def check_violation(
        self,
        *,
        current_round: int,
        total_attacks: int,
        total_tokens: int,
        total_cost: float,
        elapsed_seconds: float,
    ) -> str | None:
        """Return the first violated budget constraint, or None if all within limits."""
        if current_round >= self.max_rounds:
            return "max_rounds"
        if total_attacks >= self.max_attacks:
            return "max_attacks"
        if total_tokens >= self.max_total_tokens:
            return "max_total_tokens"
        if total_cost >= self.max_cost_usd:
            return "max_cost_usd"
        if elapsed_seconds >= self.max_duration_seconds:
            return "max_duration_seconds"
        return None


@dataclass(frozen=True, slots=True)
class AttackLineage:
    """Tracks parent-child relationships between attacks.

    Each attack in the campaign has a lineage entry. Seed attacks
    have no parent_id. Mutated attacks reference their parent's
    lineage_id.
    """

    lineage_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    parent_lineage_id: UUIDv7 | None = None
    generation: int = 0
    mutation_strategy: str = ""
    attack_category: str = ""
    is_seed: bool = True


@dataclass(frozen=True, slots=True)
class TargetExecution:
    """Record of a single attack execution against a target model."""

    execution_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    attack_prompt: str = ""
    system_prompt: str | None = None
    target_response: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider_name: str = ""
    model_name: str = ""
    error: str | None = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class AttackEffectiveness:
    """Evaluation of an attack's effectiveness against the target.

    Combines keyword-based safety scoring with optional semantic LLM-judge
    evaluation.  ``semantic_verdict`` carries the judge's structured
    determination (SUCCESS / FAILURE / INCONCLUSIVE) when a judge is
    available, and is empty otherwise.

    ``evaluation_source`` identifies how the effectiveness was determined:
      - "semantic_judge": a semantic LLM-judge produced the verdict
      - "keyword_heuristic": no semantic judge was available; keywords used
      - "error": an execution error prevented reliable evaluation
    """

    effectiveness_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    safety_scores: tuple[SafetyScore, ...] = field(default_factory=tuple)
    overall_safety_verdict: SafetyVerdict = SafetyVerdict.SAFE
    metric_score: float = 0.0
    is_violation: bool = False
    is_violation_severe: bool = False
    effectiveness_score: float = 0.0
    reasoning: str = ""
    evaluation_source: str = "keyword_heuristic"  # "semantic_judge" | "keyword_heuristic" | "error"
    # Semantic judge fields
    semantic_verdict: str = ""  # "SUCCESS" | "FAILURE" | "INCONCLUSIVE" | ""
    semantic_score: float = 0.0
    semantic_confidence: float = 0.0
    semantic_reasoning: str = ""
    semantic_evidence: str = ""
    semantic_judge_model: str = ""
    semantic_judge_cost_usd: float = 0.0
    semantic_judge_tokens_input: int = 0
    semantic_judge_tokens_output: int = 0
    semantic_judge_latency_ms: int = 0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Canonical general-metric representation of the semantic judgment.
    # Produced alongside the domain fields by AttackEvaluator and persisted
    # to the metric_results table so red-team runs are visible through the
    # canonical /metrics pipeline.
    semantic_metric_result: MetricResult | None = None


@dataclass(frozen=True, slots=True)
class CampaignRound:
    """A single round in the adaptive campaign loop.

    Each round contains one or more attacks (generated from the same
    mutation strategy) and their evaluations.
    """

    round_id: UUIDv7 = field(default_factory=UUIDv7.generate)
    round_number: int = 0
    attack_category: AttackCategory = AttackCategory.PROMPT_INJECTION
    mutation_strategy: str = ""
    mutation_phase: MutationPhase = MutationPhase.EXPLORATION
    attack_scenario: AttackScenario = field(default_factory=AttackScenario)
    lineage: AttackLineage = field(default_factory=AttackLineage)
    execution: TargetExecution | None = None
    effectiveness: AttackEffectiveness | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class CampaignResult:
    """Terminal result of an adaptive campaign."""

    campaign_id: str = ""
    state: CampaignState = CampaignState.COMPLETED
    total_rounds: int = 0
    total_attacks: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    final_effectiveness: float = 0.0
    peak_effectiveness: float = 0.0
    violation_count: int = 0
    severe_violation_count: int = 0
    rounds: tuple[CampaignRound, ...] = field(default_factory=tuple)
    budget_violation_reason: str | None = None
    category_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AdaptiveCampaign(AggregateRoot, VersionMixin):
    """Aggregate root for an adaptive red team campaign.

    Orchestrates the full campaign lifecycle: creation, budgeting,
    round execution, lineage tracking, and result aggregation.
    """

    def __init__(
        self,
        *,
        entity_id: UUIDv7 | None = None,
        name: str = "",
        description: str = "",
        target_provider: str = "",
        target_model: str = "",
        attack_categories: tuple[AttackCategory, ...] = (),
        budget: CampaignBudget | None = None,
        mutation_phase: MutationPhase = MutationPhase.EXPLORATION,
        state: CampaignState = CampaignState.CREATED,
        rounds: tuple[CampaignRound, ...] = (),
        total_tokens: int = 0,
        total_cost_usd: float = 0.0,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        super().__init__(entity_id=entity_id)
        VersionMixin.__init__(self)
        self._name = name
        self._description = description
        self._target_provider = target_provider
        self._target_model = target_model
        self._attack_categories = attack_categories or (
            AttackCategory.PROMPT_INJECTION,
            AttackCategory.JAILBREAK,
        )
        self._budget = budget or CampaignBudget()
        self._mutation_phase = mutation_phase
        self._state = state
        self._rounds: list[CampaignRound] = list(rounds)
        self._total_tokens = total_tokens
        self._total_cost_usd = total_cost_usd
        self._started_at = started_at
        self._completed_at = completed_at

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def target_provider(self) -> str:
        return self._target_provider

    @property
    def target_model(self) -> str:
        return self._target_model

    @property
    def attack_categories(self) -> tuple[AttackCategory, ...]:
        return self._attack_categories

    @property
    def budget(self) -> CampaignBudget:
        return self._budget

    @property
    def mutation_phase(self) -> MutationPhase:
        return self._mutation_phase

    @property
    def state(self) -> CampaignState:
        return self._state

    @property
    def rounds(self) -> tuple[CampaignRound, ...]:
        return tuple(self._rounds)

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def total_cost_usd(self) -> float:
        return self._total_cost_usd

    @property
    def started_at(self) -> datetime | None:
        return self._started_at

    @property
    def completed_at(self) -> datetime | None:
        return self._completed_at

    @property
    def current_round_number(self) -> int:
        return len(self._rounds)

    @property
    def elapsed_seconds(self) -> float:
        if self._started_at is None:
            return 0.0
        end = self._completed_at or datetime.now(UTC)
        return (end - self._started_at).total_seconds()

    @classmethod
    def create(
        cls,
        *,
        name: str,
        description: str = "",
        target_provider: str,
        target_model: str,
        attack_categories: tuple[AttackCategory, ...] = (),
        budget: CampaignBudget | None = None,
    ) -> AdaptiveCampaign:
        """Create a new adaptive campaign."""
        if not name or not name.strip():
            from app.kernel.exceptions.errors import ValidationError

            raise ValidationError(message="Campaign name is required", field="name")
        if not target_provider:
            from app.kernel.exceptions.errors import ValidationError

            raise ValidationError(message="Target provider is required", field="target_provider")
        if not target_model:
            from app.kernel.exceptions.errors import ValidationError

            raise ValidationError(message="Target model is required", field="target_model")

        campaign = cls(
            name=name.strip(),
            description=description.strip(),
            target_provider=target_provider,
            target_model=target_model,
            attack_categories=attack_categories or (),
            budget=budget or CampaignBudget(),
        )
        campaign.raise_event(
            AttackRunCreated(
                run_id=campaign.id,
                attack_count=0,
            ),
        )
        return campaign

    def start(self) -> None:
        """Transition campaign to running state."""
        if self._state != CampaignState.CREATED:
            raise ConflictError(
                message=f"Cannot start campaign in {self._state.value} state",
                details={"campaign_id": str(self.id), "state": self._state.value},
            )
        self._state = CampaignState.RUNNING
        self._started_at = datetime.now(UTC)
        self.increment_version()
        self.raise_event(
            AttackRunStarted(
                run_id=self.id,
                items_total=self._budget.max_attacks,
            ),
        )

    def complete(self) -> None:
        """Transition campaign to completed state."""
        if not self._state.is_active:
            raise ConflictError(
                message=f"Cannot complete campaign in {self._state.value} state",
                details={"campaign_id": str(self.id), "state": self._state.value},
            )
        self._state = CampaignState.COMPLETED
        self._completed_at = datetime.now(UTC)
        self.increment_version()
        self.raise_event(
            AttackRunCompleted(
                run_id=self.id,
                items_total=self._budget.max_attacks,
                items_completed=self.current_round_number,
            ),
        )

    def fail(self, reason: str = "") -> None:
        """Transition campaign to failed state."""
        if self._state.is_terminal:
            raise ConflictError(
                message=f"Cannot fail campaign in {self._state.value} state",
                details={"campaign_id": str(self.id), "state": self._state.value},
            )
        self._state = CampaignState.FAILED
        self._completed_at = datetime.now(UTC)
        self.increment_version()
        self.raise_event(
            AttackRunFailed(
                run_id=self.id,
                error_message=reason,
            ),
        )

    def exhaust_budget(self, reason: str) -> None:
        """Transition campaign to budget-exhausted state."""
        if self._state.is_terminal:
            raise ConflictError(
                message=f"Cannot exhaust budget in {self._state.value} state",
                details={"campaign_id": str(self.id), "state": self._state.value},
            )
        self._state = CampaignState.BUDGET_EXHAUSTED
        self._completed_at = datetime.now(UTC)
        self.increment_version()
        self.raise_event(
            AttackRunCompleted(
                run_id=self.id,
                items_total=self._budget.max_attacks,
                items_completed=self.current_round_number,
            ),
        )

    def record_round(self, campaign_round: CampaignRound) -> None:
        """Record a completed round in the campaign."""
        if self._state != CampaignState.RUNNING:
            raise DomainError(
                message=f"Cannot record round in {self._state.value} state",
            )
        self._rounds.append(campaign_round)
        self._total_tokens += campaign_round.tokens_used
        self._total_cost_usd += campaign_round.cost_usd
        self.increment_version()

    def can_continue(self) -> bool:
        """Check if the campaign can continue based on budget."""
        return self._budget.is_within_limits(
            current_round=self.current_round_number,
            total_attacks=self.current_round_number,
            total_tokens=self._total_tokens,
            total_cost=self._total_cost_usd,
            elapsed_seconds=self.elapsed_seconds,
        )

    def check_budget_violation(self) -> str | None:
        """Check which budget constraint would be violated next."""
        return self._budget.check_violation(
            current_round=self.current_round_number,
            total_attacks=self.current_round_number,
            total_tokens=self._total_tokens,
            total_cost=self._total_cost_usd,
            elapsed_seconds=self.elapsed_seconds,
        )

    def set_mutation_phase(self, phase: MutationPhase) -> None:
        """Update the mutation strategy phase."""
        self._mutation_phase = phase
        self.increment_version()

    def build_result(self) -> CampaignResult:
        """Build the terminal campaign result from accumulated rounds."""
        rounds = tuple(self._rounds)
        total_attacks = len(rounds)

        if total_attacks == 0:
            return CampaignResult(
                campaign_id=str(self.id),
                state=self._state,
                total_rounds=0,
                total_attacks=0,
                total_tokens=self._total_tokens,
                total_cost_usd=self._total_cost_usd,
                rounds=rounds,
            )

        effectiveness_scores = [
            r.effectiveness.effectiveness_score for r in rounds if r.effectiveness is not None
        ]
        final_eff = effectiveness_scores[-1] if effectiveness_scores else 0.0
        peak_eff = max(effectiveness_scores) if effectiveness_scores else 0.0

        violation_count = sum(
            1 for r in rounds if r.effectiveness is not None and r.effectiveness.is_violation
        )
        severe_count = sum(
            1 for r in rounds if r.effectiveness is not None and r.effectiveness.is_violation_severe
        )

        total_duration = sum(r.duration_ms for r in rounds)

        category_stats: dict[str, dict[str, Any]] = {}
        for r in rounds:
            cat = r.attack_category.value
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "violations": 0, "effectiveness": []}
            category_stats[cat]["total"] += 1
            if r.effectiveness is not None:
                if r.effectiveness.is_violation:
                    category_stats[cat]["violations"] += 1
                category_stats[cat]["effectiveness"].append(r.effectiveness.effectiveness_score)

        for stats in category_stats.values():
            eff_scores = stats.pop("effectiveness")
            stats["avg_effectiveness"] = sum(eff_scores) / len(eff_scores) if eff_scores else 0.0

        budget_reason = None
        if self._state == CampaignState.BUDGET_EXHAUSTED:
            budget_reason = self.check_budget_violation()

        return CampaignResult(
            campaign_id=str(self.id),
            state=self._state,
            total_rounds=total_attacks,
            total_attacks=total_attacks,
            total_tokens=self._total_tokens,
            total_cost_usd=self._total_cost_usd,
            total_duration_ms=total_duration,
            final_effectiveness=final_eff,
            peak_effectiveness=peak_eff,
            violation_count=violation_count,
            severe_violation_count=severe_count,
            rounds=rounds,
            budget_violation_reason=budget_reason,
            category_stats=category_stats,
            completed_at=self._completed_at or datetime.now(UTC),
        )
