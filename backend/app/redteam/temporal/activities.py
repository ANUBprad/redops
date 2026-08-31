"""Temporal activities for red team campaign execution.

Delegates to AdaptiveCampaignEngine for the actual campaign loop.
Each activity resolves its own dependencies via module-level globals
configured during worker startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from temporalio import activity

from app.kernel.entities.base import UUIDv7
from app.redteam.domain.campaign import (
    AdaptiveCampaign,
    CampaignBudget,
    CampaignResult,
    CampaignRound,
)
from app.redteam.domain.enums import AttackCategory
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine
from app.redteam.engine.semantic_judge import SemanticEffectivenessJudge

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_provider_registry: Any = None
_metric_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# LLM-judge safety metrics evaluated against each attack result in production.
REDTEAM_METRIC_NAMES: tuple[str, ...] = (
    "safety",
    "prompt_injection",
    "jailbreak",
    "toxicity",
    "bias",
)


def configure_redteam_provider_registry(registry: Any) -> None:
    """Set the provider registry for campaign execution activities."""
    global _provider_registry
    _provider_registry = registry


def configure_redteam_metric_engine(engine: Any) -> None:
    """Set the metric engine for campaign execution activities."""
    global _metric_engine
    _metric_engine = engine


def configure_redteam_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Set the session factory for campaign execution activities.

    Called once during worker startup so completed campaigns can persist
    their results through the repository.
    """
    global _session_factory
    _session_factory = factory


def _get_session() -> AsyncSession:
    if _session_factory is None:
        msg = "Session factory not configured. Call configure_redteam_session_factory first."
        raise RuntimeError(msg)
    return _session_factory()


def _get_provider_registry() -> Any:
    if _provider_registry is None:
        msg = "Provider registry not configured. Call configure_redteam_provider_registry first."
        raise RuntimeError(msg)
    return _provider_registry


def _get_metric_engine() -> Any:
    if _metric_engine is None:
        msg = "Metric engine not configured. Call configure_redteam_metric_engine first."
        raise RuntimeError(msg)
    return _metric_engine


# ---------------------------------------------------------------------------
# Activity input / output dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RedTeamWorkflowInput:
    """Input for the red team campaign activity."""

    attack_run_id: str = ""
    target_provider: str = ""
    target_model: str = ""
    attack_categories: tuple[str, ...] = ()
    max_rounds: int = 10
    max_attacks: int = 100
    max_total_tokens: int = 1_000_000
    max_cost_usd: float = 50.0
    max_duration_seconds: int = 3600
    effectiveness_threshold: float = 0.8


@dataclass(frozen=True, slots=True)
class FindingPayload:
    """Serializable finding from a campaign round."""

    round_number: int = 0
    attack_category: str = ""
    is_violation: bool = False
    is_severe: bool = False
    effectiveness_score: float = 0.0
    safety_verdict: str = ""
    attack_prompt: str = ""
    target_response: str = ""


@dataclass(frozen=True, slots=True)
class RedTeamWorkflowResult:
    """Result returned by the red team campaign activity."""

    attack_run_id: str = ""
    status: str = ""
    total_rounds: int = 0
    violation_count: int = 0
    severe_violation_count: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    final_effectiveness: float = 0.0
    peak_effectiveness: float = 0.0
    findings: tuple[FindingPayload, ...] = ()
    error: str = ""


def _build_findings(result: CampaignResult) -> tuple[FindingPayload, ...]:
    """Extract violation findings from campaign rounds."""
    findings: list[FindingPayload] = []
    for r in result.rounds:
        if r.effectiveness is None:
            continue
        eff = r.effectiveness
        if not eff.is_violation:
            continue
        findings.append(
            FindingPayload(
                round_number=r.round_number,
                attack_category=r.attack_category.value,
                is_violation=eff.is_violation,
                is_severe=eff.is_violation_severe,
                effectiveness_score=eff.effectiveness_score,
                safety_verdict=eff.overall_safety_verdict.value,
                attack_prompt=r.execution.attack_prompt if r.execution else "",
                target_response=r.execution.target_response if r.execution else "",
            )
        )
    return tuple(findings)


def _build_result(attack_run_id: str, result: CampaignResult) -> RedTeamWorkflowResult:
    """Map a CampaignResult to a serializable workflow result."""
    return RedTeamWorkflowResult(
        attack_run_id=attack_run_id,
        status=result.state.value,
        total_rounds=result.total_rounds,
        violation_count=result.violation_count,
        severe_violation_count=result.severe_violation_count,
        total_tokens=result.total_tokens,
        total_cost_usd=result.total_cost_usd,
        final_effectiveness=result.final_effectiveness,
        peak_effectiveness=result.peak_effectiveness,
        findings=_build_findings(result),
    )


def _campaign_to_dict(result: CampaignResult) -> dict[str, Any]:
    """Serialize a CampaignResult to a JSON-safe dict.

    Preserves per-round prompts/responses/effectiveness and the
    semantic judge data captured in each round so the completed
    campaign is durable and retrievable through the repository.
    """
    return {
        "campaign_id": result.campaign_id,
        "state": result.state.value,
        "total_rounds": result.total_rounds,
        "total_attacks": result.total_attacks,
        "total_tokens": result.total_tokens,
        "total_cost_usd": result.total_cost_usd,
        "total_duration_ms": result.total_duration_ms,
        "final_effectiveness": result.final_effectiveness,
        "peak_effectiveness": result.peak_effectiveness,
        "violation_count": result.violation_count,
        "severe_violation_count": result.severe_violation_count,
        "budget_violation_reason": result.budget_violation_reason,
        "category_stats": result.category_stats,
        "completed_at": _jsonable(result.completed_at),
        "rounds": [_round_to_dict(r) for r in result.rounds],
    }


def _round_to_dict(round_: CampaignRound) -> dict[str, Any]:
    execution = round_.execution
    effectiveness = round_.effectiveness
    return {
        "round_id": _jsonable(round_.round_id),
        "round_number": round_.round_number,
        "attack_category": round_.attack_category.value,
        "mutation_strategy": round_.mutation_strategy,
        "mutation_phase": round_.mutation_phase.value,
        "attack_scenario": _scenario_to_dict(round_.attack_scenario),
        "lineage": {
            "lineage_id": _jsonable(round_.lineage.lineage_id),
            "parent_lineage_id": _jsonable(round_.lineage.parent_lineage_id),
            "generation": round_.lineage.generation,
            "mutation_strategy": round_.lineage.mutation_strategy,
            "attack_category": round_.lineage.attack_category,
            "is_seed": round_.lineage.is_seed,
        },
        "execution": _execution_to_dict(execution) if execution else None,
        "effectiveness": _effectiveness_to_dict(effectiveness) if effectiveness else None,
        "tokens_used": round_.tokens_used,
        "cost_usd": round_.cost_usd,
        "duration_ms": round_.duration_ms,
    }


def _scenario_to_dict(scenario: Any) -> dict[str, Any]:
    return {
        "scenario_id": _jsonable(scenario.scenario_id),
        "attack_definition_id": _jsonable(scenario.attack_definition_id),
        "template_name": scenario.template_name,
        "category": scenario.category.value,
        "severity": scenario.severity.value,
        "prompt": scenario.prompt,
        "system_prompt_override": scenario.system_prompt_override,
        "expected_behavior": scenario.expected_behavior,
        "parameters": scenario.parameters,
        "turn_index": scenario.turn_index,
        "metadata": scenario.metadata,
    }


def _execution_to_dict(execution: Any) -> dict[str, Any]:
    return {
        "execution_id": _jsonable(execution.execution_id),
        "attack_prompt": execution.attack_prompt,
        "system_prompt": execution.system_prompt,
        "target_response": execution.target_response,
        "tokens_input": execution.tokens_input,
        "tokens_output": execution.tokens_output,
        "total_tokens": execution.total_tokens,
        "cost_usd": execution.cost_usd,
        "latency_ms": execution.latency_ms,
        "provider_name": execution.provider_name,
        "model_name": execution.model_name,
        "error": execution.error,
        "executed_at": _jsonable(execution.executed_at),
    }


def _effectiveness_to_dict(effectiveness: Any) -> dict[str, Any]:
    return {
        "effectiveness_id": _jsonable(effectiveness.effectiveness_id),
        "safety_scores": [
            {
                "dimension": s.dimension.value,
                "score": s.score,
                "normalized_score": s.normalized_score,
                "verdict": s.verdict.value,
                "reasoning": s.reasoning,
                "confidence": s.confidence,
            }
            for s in effectiveness.safety_scores
        ],
        "overall_safety_verdict": effectiveness.overall_safety_verdict.value,
        "metric_score": effectiveness.metric_score,
        "is_violation": effectiveness.is_violation,
        "is_violation_severe": effectiveness.is_violation_severe,
        "effectiveness_score": effectiveness.effectiveness_score,
        "reasoning": effectiveness.reasoning,
        "evaluation_source": effectiveness.evaluation_source,
        "semantic_verdict": effectiveness.semantic_verdict,
        "semantic_score": effectiveness.semantic_score,
        "semantic_confidence": effectiveness.semantic_confidence,
        "semantic_reasoning": effectiveness.semantic_reasoning,
        "semantic_evidence": effectiveness.semantic_evidence,
        "semantic_judge_model": effectiveness.semantic_judge_model,
        "semantic_judge_cost_usd": effectiveness.semantic_judge_cost_usd,
        "semantic_judge_tokens_input": effectiveness.semantic_judge_tokens_input,
        "semantic_judge_tokens_output": effectiveness.semantic_judge_tokens_output,
        "semantic_judge_latency_ms": effectiveness.semantic_judge_latency_ms,
        "evaluated_at": _jsonable(effectiveness.evaluated_at),
    }


def _jsonable(value: Any) -> Any:
    """Convert domain leaf values (UUIDv7, enum, datetime, None) to JSON-safe."""
    if value is None:
        return None
    if isinstance(value, UUIDv7):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn
async def red_team_campaign_activity(
    input: RedTeamWorkflowInput,
) -> RedTeamWorkflowResult:
    """Execute a full red team campaign via AdaptiveCampaignEngine.

    Builds the campaign configuration from the input, runs the full
    generate→execute→evaluate→mutate loop, and returns aggregated
    results including all violation findings.
    """
    activity.logger.info(
        "Starting red team campaign attack_run_id=%s target=%s/%s",
        input.attack_run_id,
        input.target_provider,
        input.target_model,
    )

    if activity.in_activity():
        activity.heartbeat("building campaign")

    try:
        registry = _get_provider_registry()
        metric_engine = _get_metric_engine()

        categories: tuple[AttackCategory, ...] = ()
        if input.attack_categories:
            categories = tuple(AttackCategory(c) for c in input.attack_categories)

        budget = CampaignBudget(
            max_rounds=input.max_rounds,
            max_attacks=input.max_attacks,
            max_total_tokens=input.max_total_tokens,
            max_cost_usd=input.max_cost_usd,
            max_duration_seconds=input.max_duration_seconds,
            effectiveness_threshold=input.effectiveness_threshold,
        )

        campaign = AdaptiveCampaign.create(
            name=f"attack-run-{input.attack_run_id}",
            target_provider=input.target_provider,
            target_model=input.target_model,
            attack_categories=categories,
            budget=budget,
        )

        # The judge uses the same provider/model as the target so the
        # semantic effectiveness determination is made by a real LLM call
        # against the assigned provider, mirroring the general-eval path.
        from app.evaluation.judge.domain import JudgeConfig

        judge_provider = registry.resolve(input.target_provider)
        semantic_judge = SemanticEffectivenessJudge(
            provider=judge_provider,
            config=JudgeConfig(
                provider_name=input.target_provider,
                model=input.target_model,
                temperature=0.0,
                max_tokens=512,
            ),
        )

        engine = AdaptiveCampaignEngine(
            registry=registry,
            metric_engine=metric_engine,
            metric_names=REDTEAM_METRIC_NAMES,
            semantic_judge=semantic_judge,
            judge_provider=judge_provider,
            judge_provider_name=input.target_provider,
            judge_model=input.target_model,
        )

        if activity.in_activity():
            activity.heartbeat("running campaign loop")

        result = await engine.run_campaign(campaign)

        activity.logger.info(
            "Red team campaign completed attack_run_id=%s status=%s rounds=%d violations=%d",
            input.attack_run_id,
            result.state.value,
            result.total_rounds,
            result.violation_count,
        )

        await _persist_campaign_results(input.attack_run_id, result)

        return _build_result(input.attack_run_id, result)

    except Exception as exc:
        activity.logger.error(
            "Red team campaign failed attack_run_id=%s error=%s",
            input.attack_run_id,
            str(exc),
        )
        return RedTeamWorkflowResult(
            attack_run_id=input.attack_run_id,
            status="failed",
            error=str(exc),
        )


async def _persist_campaign_results(
    attack_run_id: str,
    result: CampaignResult,
) -> None:
    """Persist the completed campaign results to the attack run.

    Opens its own database session via the configured session factory
    and writes the full per-round results to the existing
    ``campaign_results`` JSON column, mirroring the general-eval
    persistence pattern.
    """
    from app.infrastructure.database.repositories.attack_run_repository import (
        SqlAlchemyAttackRunRepository,
    )

    campaign_json = _campaign_to_dict(result)
    async with _get_session() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        await repo.persist_campaign_results(
            UUIDv7.from_string(attack_run_id),
            campaign_json,
        )
        await session.commit()
