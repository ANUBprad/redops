"""Dashboard summary service.

Aggregates data from evaluation, run, metric, and attack repositories
to produce the dashboard summary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.analytics.domain.entities import ActivityEntry, DashboardSummary
from app.evaluation.domain.contracts.evaluation_contracts import RunQuery
from app.redteam.contracts.repositories import AttackRunQuery

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import (
        EvaluationRepository,
        MetricResultRepository,
        RunRepository,
    )
    from app.redteam.contracts.repositories import AttackRunRepository


class DashboardService:
    """Service for computing dashboard summary analytics."""

    def __init__(
        self,
        evaluation_repo: EvaluationRepository,
        run_repo: RunRepository,
        metric_repo: MetricResultRepository,
        attack_run_repo: AttackRunRepository,
    ) -> None:
        self._evaluation_repo = evaluation_repo
        self._run_repo = run_repo
        self._metric_repo = metric_repo
        self._attack_run_repo = attack_run_repo

    async def get_summary(
        self,
        project_id: str | None = None,
        days: int = 30,
    ) -> DashboardSummary:
        """Compute the dashboard summary."""
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        total_evaluations = await self._evaluation_repo.count()

        all_runs_query = RunQuery(page=1, page_size=1000)
        all_runs_result = await self._run_repo.list(all_runs_query)

        completed_count = 0
        total_cost = 0.0
        total_latency = 0.0
        latency_count = 0
        total_tokens = 0
        recent_runs = []

        for run in all_runs_result.items:
            created = run.created_at
            if created and created >= since:
                status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
                if status_val == "completed":
                    completed_count += 1
                total_cost += run.cost
                if run.average_latency_ms > 0:
                    total_latency += run.average_latency_ms
                    latency_count += 1
                total_tokens += run.token_input + run.token_output
                recent_runs.append(run)

        success_rate = (completed_count / len(recent_runs) * 100) if recent_runs else 0.0
        avg_cost = total_cost / len(recent_runs) if recent_runs else 0.0
        avg_latency = total_latency / latency_count if latency_count > 0 else 0.0

        attack_query = AttackRunQuery(page=1, page_size=1000)
        attack_result = await self._attack_run_repo.list(attack_query)

        total_attacks = 0
        total_violated = 0
        for ar in attack_result.items:
            total_attacks += ar.items_total
            total_violated += ar.items_violated

        avg_safety = (
            ((total_attacks - total_violated) / total_attacks * 100) if total_attacks > 0 else 100.0
        )
        attack_success_rate = (total_violated / total_attacks * 100) if total_attacks > 0 else 0.0

        activity = self._build_activity(recent_runs[:5], attack_result.items[:5])

        return DashboardSummary(
            total_evaluations=total_evaluations,
            completed_runs=completed_count,
            success_rate=round(success_rate, 1),
            average_score=round(avg_cost, 4),
            average_latency_ms=round(avg_latency, 1),
            average_cost=round(avg_cost, 4),
            total_token_usage=total_tokens,
            average_safety_score=round(avg_safety, 2),
            attack_success_rate=round(attack_success_rate, 1),
            recent_activity=activity,
        )

    def _build_activity(
        self,
        runs: list[object],
        attacks: list[object],
    ) -> tuple[ActivityEntry, ...]:
        """Build recent activity entries."""
        entries: list[ActivityEntry] = []

        for run in runs:
            status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
            entries.append(
                ActivityEntry(
                    id=str(run.id),
                    type="evaluation_run",
                    name=run.evaluation_name,
                    status=status_val,
                    timestamp=run.created_at,
                    summary=f"{run.items_completed}/{run.items_total} items",
                )
            )

        for attack in attacks:
            status_val = (
                attack.status.value if hasattr(attack.status, "value") else str(attack.status)
            )
            entries.append(
                ActivityEntry(
                    id=str(attack.id),
                    type="attack_run",
                    name=f"Attack Run {str(attack.id)[:8]}",
                    status=status_val,
                    timestamp=attack.created_at,
                    summary=f"{attack.items_passed} passed, {attack.items_violated} violated",
                )
            )

        entries.sort(key=lambda e: e.timestamp or datetime.min.replace(tzinfo=UTC), reverse=True)
        return tuple(entries[:10])
