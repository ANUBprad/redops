"""Leaderboard service."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.analytics.domain.entities import Leaderboard, LeaderboardEntry

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import RunRepository


class LeaderboardService:
    """Service for generating leaderboards."""

    def __init__(self, run_repo: RunRepository) -> None:
        self._run_repo = run_repo

    async def get_leaderboard(
        self,
        ranking_by: str = "score",
        project_id: str | None = None,
        provider: str | None = None,
        limit: int = 10,
        days: int = 30,
    ) -> Leaderboard:
        """Generate a leaderboard.

        Supported ranking_by values:
            - score: Highest average score
            - latency: Lowest latency
            - cost: Lowest cost
            - reliability: Highest success rate

        """
        now = datetime.now(UTC)
        since = now - timedelta(days=days)

        runs = await self._run_repo.find_by_date_range(
            since=since,
            until=now,
            provider=provider,
        )

        model_data: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "scores": [],
                "latencies": [],
                "costs": [],
                "total": 0,
                "completed": 0,
                "provider": "",
            }
        )

        for run in runs:
            m = run.model
            data = model_data[m]
            if run.average_latency_ms > 0:
                data["latencies"].append(run.average_latency_ms)
            data["costs"].append(run.cost)
            data["total"] = int(data["total"]) + run.items_total
            data["completed"] = int(data["completed"]) + run.items_completed
            data["provider"] = run.provider

        entries: list[LeaderboardEntry] = []
        for model_name, data in model_data.items():
            latencies = data["latencies"]  # type: ignore[arg-type]
            costs = data["costs"]  # type: ignore[arg-type]
            total = int(data["total"])
            completed = int(data["completed"])

            avg_score = (completed / total * 100) if total > 0 else 0.0
            avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
            avg_cost = sum(costs) / len(costs) if costs else 0.0
            reliability = (completed / total * 100) if total > 0 else 0.0

            if ranking_by == "latency":
                sort_val = avg_latency
            elif ranking_by == "cost":
                sort_val = avg_cost
            elif ranking_by == "reliability":
                sort_val = reliability
            else:
                sort_val = avg_score

            entries.append(
                LeaderboardEntry(
                    entity_id=model_name,
                    entity_name=model_name,
                    entity_type="model",
                    score=round(sort_val, 2),
                    metric_name=ranking_by,
                    metadata={"provider": str(data["provider"])},
                )
            )

        reverse = ranking_by != "latency" and ranking_by != "cost"
        entries.sort(key=lambda e: e.score, reverse=reverse)

        ranked = []
        for i, entry in enumerate(entries[:limit]):
            ranked.append(
                LeaderboardEntry(
                    rank=i + 1,
                    entity_id=entry.entity_id,
                    entity_name=entry.entity_name,
                    entity_type=entry.entity_type,
                    score=entry.score,
                    metric_name=entry.metric_name,
                    metadata=entry.metadata,
                )
            )

        title_map = {
            "score": "Top Models by Score",
            "latency": "Fastest Models",
            "cost": "Most Cost-Effective Models",
            "reliability": "Most Reliable Models",
        }

        return Leaderboard(
            title=title_map.get(ranking_by, f"Leaderboard: {ranking_by}"),
            ranking_by=ranking_by,
            entries=tuple(ranked),
            generated_at=now,
        )
