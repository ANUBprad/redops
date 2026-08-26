"""Adaptive campaign engine — the core red team campaign loop.

Orchestrates: Attack Generation → Target Execution → Response →
Effectiveness Evaluation → Mutation/Strategy Selection → Next Attack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.redteam.domain.campaign import (
    AdaptiveCampaign,
    AttackLineage,
    CampaignResult,
    CampaignRound,
)
from app.redteam.domain.campaign_enums import CampaignState, MutationPhase
from app.redteam.domain.enums import AttackCategory
from app.redteam.domain.value_objects import AttackScenario
from app.redteam.engine.attack_evaluator import AttackEvaluator
from app.redteam.engine.mutation_selector import MutationStrategySelector
from app.redteam.engine.orchestrator import AttackOrchestrator
from app.redteam.engine.target_executor import TargetExecutor

if TYPE_CHECKING:
    from app.evaluation.metrics.engine import MetricEngine
    from app.providers.registry.registry import ProviderRegistry
    from app.redteam.engine.semantic_judge import SemanticEffectivenessJudge


class AdaptiveCampaignEngine:
    """Orchestrates the complete adaptive red team campaign loop.

    The loop:
    1. Generate attack scenarios (via AttackOrchestrator)
    2. Optionally mutate prompts (via MutationStrategySelector)
    3. Execute against target (via TargetExecutor → ProviderRegistry)
    4. Evaluate effectiveness (via AttackEvaluator → MetricEngine)
    5. Select next mutation strategy (via MutationStrategySelector)
    6. Repeat until budget exhausted or effectiveness threshold met
    7. Produce terminal CampaignResult
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        metric_engine: MetricEngine | None = None,
        metric_names: tuple[str, ...] = (),
        semantic_judge: SemanticEffectivenessJudge | None = None,
    ) -> None:
        self._registry = registry
        self._orchestrator = AttackOrchestrator()
        self._executor = TargetExecutor(registry)
        self._evaluator = AttackEvaluator(metric_engine, metric_names, semantic_judge)
        self._selector = MutationStrategySelector()

    @property
    def orchestrator(self) -> AttackOrchestrator:
        return self._orchestrator

    @property
    def executor(self) -> TargetExecutor:
        return self._executor

    @property
    def evaluator(self) -> AttackEvaluator:
        return self._evaluator

    @property
    def selector(self) -> MutationStrategySelector:
        return self._selector

    async def run_campaign(self, campaign: AdaptiveCampaign) -> CampaignResult:
        """Execute the full adaptive campaign loop.

        This is the primary entry point. Runs the campaign from
        CREATED through to a terminal state.
        """
        campaign.start()

        try:
            while campaign.can_continue():
                campaign_round = await self._execute_round(campaign)
                campaign.record_round(campaign_round)

                if self._should_stop_early(campaign, campaign_round):
                    break

                phase_recommendation = self._selector.recommend_phase_transition(
                    list(campaign.rounds),
                    campaign.mutation_phase,
                )
                if phase_recommendation is not None:
                    campaign.set_mutation_phase(phase_recommendation)

            if campaign.state == CampaignState.RUNNING:
                if not campaign.can_continue():
                    violation = campaign.check_budget_violation()
                    campaign.exhaust_budget(violation or "unknown")
                else:
                    campaign.complete()

        except Exception as exc:
            if campaign.state.is_active:
                campaign.fail(str(exc))

        return campaign.build_result()

    async def _execute_round(self, campaign: AdaptiveCampaign) -> CampaignRound:
        """Execute a single round of the campaign loop."""
        category = self._select_category(campaign)
        strategy = self._selector.select_strategy(
            campaign.mutation_phase,
            list(campaign.rounds),
        )

        scenario = await self._generate_scenario(campaign, category)

        mutation_result = None
        if campaign.current_round_number > 0:
            mutation_result = await self._selector.apply_mutation(
                scenario.prompt,
                strategy,
            )
            scenario = AttackScenario(
                template_name=scenario.template_name,
                category=scenario.category,
                severity=scenario.severity,
                prompt=mutation_result.mutated_prompt,
                system_prompt_override=scenario.system_prompt_override,
                expected_behavior=scenario.expected_behavior,
                parameters=scenario.parameters,
            )

        lineage = AttackLineage(
            parent_lineage_id=(campaign.rounds[-1].lineage.lineage_id if campaign.rounds else None),
            generation=campaign.current_round_number,
            mutation_strategy=strategy.value,
            attack_category=category.value,
            is_seed=campaign.current_round_number == 0,
        )

        execution, attack_result = await self._executor.execute(
            scenario,
            provider_name=campaign.target_provider,
            model=campaign.target_model,
        )

        effectiveness = await self._evaluator.evaluate(attack_result)

        duration_ms = execution.latency_ms

        return CampaignRound(
            round_number=campaign.current_round_number + 1,
            attack_category=category,
            mutation_strategy=strategy.value,
            mutation_phase=campaign.mutation_phase,
            attack_scenario=scenario,
            lineage=lineage,
            execution=execution,
            effectiveness=effectiveness,
            tokens_used=execution.total_tokens,
            cost_usd=execution.cost_usd,
            duration_ms=duration_ms,
        )

    async def _generate_scenario(
        self,
        campaign: AdaptiveCampaign,
        category: AttackCategory,
    ) -> AttackScenario:
        """Generate an attack scenario for the given category."""
        scenarios = await self._orchestrator.generate_scenarios(
            category=category,
            template={},
            parameters={},
            count=1,
        )
        return (
            scenarios[0]
            if scenarios
            else AttackScenario(
                category=category,
                prompt=f"Default {category.value} attack",
            )
        )

    def _select_category(self, campaign: AdaptiveCampaign) -> AttackCategory:
        """Select an attack category, rotating through configured categories."""
        categories = campaign.attack_categories
        if not categories:
            return AttackCategory.PROMPT_INJECTION

        idx = campaign.current_round_number % len(categories)
        return categories[idx]

    def _should_stop_early(
        self,
        campaign: AdaptiveCampaign,
        campaign_round: CampaignRound,
    ) -> bool:
        """Check if the campaign should stop before budget exhaustion."""
        if campaign_round.effectiveness is None:
            return False

        if (
            campaign_round.effectiveness.effectiveness_score
            >= campaign.budget.effectiveness_threshold
        ):
            return True

        if campaign_round.execution is not None and campaign_round.execution.error is not None:
            consecutive_errors = self._count_consecutive_errors(campaign)
            if consecutive_errors >= 3:
                return True

        return False

    def _count_consecutive_errors(self, campaign: AdaptiveCampaign) -> int:
        """Count consecutive execution errors from most recent round."""
        count = 0
        for r in reversed(campaign.rounds):
            if r.execution is not None and r.execution.error is not None:
                count += 1
            else:
                break
        return count

    async def run_single_attack(
        self,
        campaign: AdaptiveCampaign,
        category: AttackCategory,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> CampaignRound:
        """Execute a single attack outside the campaign loop.

        Useful for testing individual attacks without running the
        full adaptive loop.
        """
        scenario = AttackScenario(
            category=category,
            prompt=prompt,
            system_prompt_override=system_prompt,
        )

        lineage = AttackLineage(
            generation=0,
            attack_category=category.value,
            is_seed=True,
        )

        execution, attack_result = await self._executor.execute(
            scenario,
            provider_name=campaign.target_provider,
            model=campaign.target_model,
        )

        effectiveness = await self._evaluator.evaluate(attack_result)

        return CampaignRound(
            round_number=1,
            attack_category=category,
            mutation_strategy="direct",
            mutation_phase=MutationPhase.EXPLORATION,
            attack_scenario=scenario,
            lineage=lineage,
            execution=execution,
            effectiveness=effectiveness,
            tokens_used=execution.total_tokens,
            cost_usd=execution.cost_usd,
            duration_ms=execution.latency_ms,
        )
