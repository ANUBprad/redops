"""Mutation strategy selector — adaptive strategy selection.

Selects mutation strategies based on campaign history, phase,
and effectiveness feedback. Uses the existing MutationEngine
and AdaptiveRefiner for strategy application and refinement.
"""

from __future__ import annotations

import random
from typing import Any

from app.redteam.domain.campaign import CampaignRound
from app.redteam.domain.campaign_enums import MutationPhase
from app.redteam.engine.mutation import (
    AdaptiveRefiner,
    MutationEngine,
    MutationResult,
    MutationStrategy,
)


class MutationStrategySelector:
    """Selects mutation strategies adaptively based on campaign history.

    Operates in three phases:
    - EXPLORATION: Try diverse strategies to discover what works
    - EXPLOITATION: Focus on strategies that have been effective
    - ADAPTIVE: Balance exploration and exploitation based on feedback
    """

    def __init__(self, mutation_engine: MutationEngine | None = None) -> None:
        self._mutation_engine = mutation_engine or MutationEngine()
        self._refiner = AdaptiveRefiner()
        self._strategy_history: list[tuple[str, float]] = []

    @property
    def mutation_engine(self) -> MutationEngine:
        return self._mutation_engine

    def select_strategy(
        self,
        phase: MutationPhase,
        rounds: list[CampaignRound],
        *,
        exploration_rate: float = 0.3,
    ) -> MutationStrategy:
        """Select the next mutation strategy based on phase and history.

        Args:
            phase: Current mutation phase.
            rounds: History of completed rounds.
            exploration_rate: Probability of exploring a new strategy
                during ADAPTIVE phase.

        Returns:
            Selected MutationStrategy.

        """
        if phase == MutationPhase.EXPLORATION:
            return self._select_exploration(rounds)
        if phase == MutationPhase.EXPLOITATION:
            return self._select_exploitation(rounds)
        return self._select_adaptive(rounds, exploration_rate=exploration_rate)

    def _select_exploration(self, rounds: list[CampaignRound]) -> MutationStrategy:
        """Select a strategy that hasn't been tried recently."""
        recent_strategies = {
            r.mutation_strategy for r in rounds[-5:]
        } if rounds else set()

        all_strategies = list(MutationStrategy)
        untried = [s for s in all_strategies if s.value not in recent_strategies]

        if untried:
            return random.choice(untried)
        return random.choice(all_strategies)

    def _select_exploitation(self, rounds: list[CampaignRound]) -> MutationStrategy:
        """Select the strategy with the highest historical effectiveness."""
        if not rounds:
            return MutationStrategy.ROLE_CONFUSION

        strategy_scores: dict[str, list[float]] = {}
        for r in rounds:
            if r.effectiveness is not None:
                strat = r.mutation_strategy
                if strat not in strategy_scores:
                    strategy_scores[strat] = []
                strategy_scores[strat].append(r.effectiveness.effectiveness_score)

        if not strategy_scores:
            return MutationStrategy.ROLE_CONFUSION

        avg_scores = {
            s: sum(scores) / len(scores)
            for s, scores in strategy_scores.items()
        }

        best_strategy = max(avg_scores, key=avg_scores.get)  # type: ignore[arg-type]
        try:
            return MutationStrategy(best_strategy)
        except ValueError:
            return MutationStrategy.ROLE_CONFUSION

    def _select_adaptive(
        self,
        rounds: list[CampaignRound],
        *,
        exploration_rate: float = 0.3,
    ) -> MutationStrategy:
        """Balance exploration and exploitation based on feedback."""
        if random.random() < exploration_rate:
            return self._select_exploration(rounds)
        return self._select_exploitation(rounds)

    async def apply_mutation(
        self,
        prompt: str,
        strategy: MutationStrategy,
        *,
        context: dict[str, Any] | None = None,
    ) -> MutationResult:
        """Apply a mutation strategy to a prompt."""
        results = await self._mutation_engine.mutate(
            prompt,
            strategy,
            count=1,
            context=context,
        )
        return results[0] if results else MutationResult(
            original_prompt=prompt,
            mutated_prompt=prompt,
            strategy=strategy,
        )

    def analyze_history(self, rounds: list[CampaignRound]) -> dict[str, Any]:
        """Analyze campaign history to provide insights.

        Includes semantic verdict counts when available, giving a more
        accurate picture of which strategies actually succeed vs. which
        merely trigger keyword matches.
        """
        if not rounds:
            return {
                "total_rounds": 0,
                "strategy_effectiveness": {},
                "best_strategy": None,
                "trend": "insufficient_data",
                "semantic_successes": 0,
                "semantic_failures": 0,
                "semantic_inconclusive": 0,
            }

        strategy_effectiveness: dict[str, list[float]] = {}
        semantic_successes = 0
        semantic_failures = 0
        semantic_inconclusive = 0

        for r in rounds:
            if r.effectiveness is not None:
                strat = r.mutation_strategy
                if strat not in strategy_effectiveness:
                    strategy_effectiveness[strat] = []
                strategy_effectiveness[strat].append(r.effectiveness.effectiveness_score)

                # Count semantic verdicts
                sv = r.effectiveness.semantic_verdict
                if sv == "SUCCESS":
                    semantic_successes += 1
                elif sv == "FAILURE":
                    semantic_failures += 1
                elif sv == "INCONCLUSIVE":
                    semantic_inconclusive += 1

        avg_effectiveness = {
            s: sum(scores) / len(scores)
            for s, scores in strategy_effectiveness.items()
        }

        best = max(avg_effectiveness, key=avg_effectiveness.get) if avg_effectiveness else None  # type: ignore[arg-type]

        recent = rounds[-3:] if len(rounds) >= 3 else rounds
        recent_eff = [
            r.effectiveness.effectiveness_score
            for r in recent
            if r.effectiveness is not None
        ]
        if len(recent_eff) >= 2:
            trend = "improving" if recent_eff[-1] > recent_eff[0] else "declining"
        else:
            trend = "stable"

        return {
            "total_rounds": len(rounds),
            "strategy_effectiveness": avg_effectiveness,
            "best_strategy": best,
            "trend": trend,
            "semantic_successes": semantic_successes,
            "semantic_failures": semantic_failures,
            "semantic_inconclusive": semantic_inconclusive,
        }

    def recommend_phase_transition(
        self,
        rounds: list[CampaignRound],
        current_phase: MutationPhase,
    ) -> MutationPhase | None:
        """Recommend when to transition between mutation phases.

        Uses semantic verdicts when available for more accurate
        phase transitions. Semantic SUCCESS counts as a strong
        signal to exploit; semantic FAILURE counts as a signal
        that the current strategy is not working.
        """
        if len(rounds) < 3:
            return None

        analysis = self.analyze_history(rounds)
        trend = analysis.get("trend", "stable")
        semantic_successes = analysis.get("semantic_successes", 0)
        semantic_failures = analysis.get("semantic_failures", 0)

        if current_phase == MutationPhase.EXPLORATION:
            # If we have enough semantic successes, move to exploitation
            if semantic_successes >= 2 and len(rounds) >= 5:
                return MutationPhase.EXPLOITATION
            # Standard transition: enough rounds and not improving
            if len(rounds) >= 5 and trend != "improving":
                return MutationPhase.EXPLOITATION

        if current_phase == MutationPhase.EXPLOITATION:
            # If we have semantic failures, go back to exploration
            if semantic_failures >= 2:
                return MutationPhase.EXPLORATION
            # Standard transition: declining trend
            if trend == "declining":
                return MutationPhase.EXPLORATION

        return None
