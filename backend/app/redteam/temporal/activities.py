"""Temporal activities for red team campaign execution.

Delegates to AdaptiveCampaignEngine for the actual campaign loop.
Each activity resolves its own dependencies via module-level globals
configured during worker startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from temporalio import activity

from app.redteam.domain.campaign import AdaptiveCampaign, CampaignBudget, CampaignResult
from app.redteam.domain.enums import AttackCategory
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine

_provider_registry: Any = None


def configure_redteam_provider_registry(registry: Any) -> None:
    """Set the provider registry for campaign execution activities."""
    global _provider_registry
    _provider_registry = registry


def _get_provider_registry() -> Any:
    if _provider_registry is None:
        msg = "Provider registry not configured. Call configure_redteam_provider_registry first."
        raise RuntimeError(msg)
    return _provider_registry


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

        engine = AdaptiveCampaignEngine(registry=registry)

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
