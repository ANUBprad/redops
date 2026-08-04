"""Safety analytics service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.analytics.domain.entities import (
    DimensionScore,
    SafetyTrend,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.redteam.contracts.repositories import AttackRunRepository
    from app.redteam.domain.entities import AttackRun


class SafetyService:
    """Service for safety analytics."""

    def __init__(self, attack_run_repo: AttackRunRepository) -> None:
        self._attack_run_repo = attack_run_repo

    async def get_safety_trend(
        self,
        project_id: str | None = None,
        category: str | None = None,
        days: int = 30,
    ) -> SafetyTrend:
        """Compute safety trend analysis."""
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        attack_runs = await self._attack_run_repo.find_by_date_range(
            since=since,
            until=now,
        )

        total_attacks = sum(r.items_total for r in attack_runs)
        total_violations = sum(r.items_violated for r in attack_runs)
        total_passed = sum(r.items_passed for r in attack_runs)

        violation_rate = (total_violations / total_attacks * 100) if total_attacks > 0 else 0.0
        pass_rate = (total_passed / total_attacks * 100) if total_attacks > 0 else 0.0
        avg_safety = 100.0 - violation_rate

        dimensions = await self._compute_dimension_scores(attack_runs)

        return SafetyTrend(
            average_safety_score=round(avg_safety, 2),
            violation_rate=round(violation_rate, 2),
            pass_rate=round(pass_rate, 2),
            safety_by_dimension=dimensions,
            total_attacks=total_attacks,
            total_violations=total_violations,
        )

    async def _compute_dimension_scores(
        self,
        attack_runs: Sequence[AttackRun],
    ) -> tuple[DimensionScore, ...]:
        """Compute safety scores by dimension."""
        from app.redteam.domain.enums import SafetyDimension

        dimensions = []
        for dim in SafetyDimension:
            dim_name = dim.value if hasattr(dim, "value") else str(dim)
            total = sum(getattr(r, "items_total", 0) for r in attack_runs)
            violated = sum(getattr(r, "items_violated", 0) for r in attack_runs)

            score = ((total - violated) / total * 100) if total > 0 else 100.0
            verdict = "safe" if score >= 90 else "suspicious" if score >= 70 else "violated"

            dimensions.append(
                DimensionScore(
                    dimension=dim_name,
                    score=round(score, 2),
                    verdict=verdict,
                    sample_count=total,
                )
            )

        return tuple(dimensions)
