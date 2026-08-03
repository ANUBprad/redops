"""Command and query handlers for the metrics engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.metrics.commands import (
    GetAggregatedScoresQuery,
    GetItemMetricResultsQuery,
    GetMetricResultsQuery,
    ListAvailableMetricsQuery,
    ScoreBatchCommand,
    ScoreItemCommand,
)
from app.evaluation.metrics.domain import (
    MetricAggregation,
    MetricInput,
    MetricResult,
)
from app.evaluation.metrics.engine import MetricEngine
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ValidationError

if TYPE_CHECKING:
    from app.evaluation.domain.contracts.evaluation_contracts import MetricResultRepository
    from app.evaluation.metrics.domain import MetricDefinition


class ScoreItemHandler:
    """Handler for scoring a single evaluation item."""

    def __init__(
        self,
        engine: MetricEngine,
        repository: MetricResultRepository,
    ) -> None:
        """Initialize with engine and repository."""
        self._engine = engine
        self._repository = repository

    async def handle(self, command: ScoreItemCommand) -> list[MetricResult]:
        """Execute the score item command.

        Args:
            command: The score command.

        Returns:
            List of MetricResults for each evaluated metric.

        """
        run_id = UUIDv7.from_string(command.run_id)
        item_id = UUIDv7.from_string(command.item_id)

        metric_names = command.metric_names
        if not metric_names:
            metric_names = tuple(d.name for d in self._engine.list_definitions())

        resolved = self._engine.resolve_metrics(metric_names)
        if not resolved:
            return []

        input_data = MetricInput(
            prompt=command.prompt,
            response=command.response,
            reference=command.reference,
            context=command.context,
            tool_calls=command.tool_calls,
            metadata={
                **command.metadata,
                "run_id": str(run_id),
                "item_id": str(item_id),
            },
        )

        results = await self._engine.evaluate_batch(resolved, input_data)

        enriched: list[MetricResult] = []
        for r in results:
            if not r.is_success:
                continue
            enriched.append(
                MetricResult(
                    metric_name=r.metric_name,
                    score=r.score,
                    normalized_score=r.normalized_score,
                    raw_output=r.raw_output,
                    reasoning=r.reasoning,
                    metadata={
                        **r.metadata,
                        "run_id": str(run_id),
                        "item_id": str(item_id),
                    },
                    execution_time_ms=r.execution_time_ms,
                    error=r.error,
                ),
            )

        if enriched:
            await self._repository.save_many(enriched)

        return list(results)


class ScoreBatchHandler:
    """Handler for scoring multiple items."""

    def __init__(self, score_item_handler: ScoreItemHandler) -> None:
        """Initialize with the single-item handler."""
        self._score_item_handler = score_item_handler

    async def handle(self, command: ScoreBatchCommand) -> list[MetricResult]:
        """Execute the batch score command.

        Args:
            command: The batch score command.

        Returns:
            Combined list of all MetricResults.

        """
        all_results: list[MetricResult] = []
        for item in command.items:
            results = await self._score_item_handler.handle(item)
            all_results.extend(results)
        return all_results


class GetMetricResultsHandler:
    """Handler for retrieving metric results."""

    def __init__(self, repository: MetricResultRepository) -> None:
        """Initialize with repository."""
        self._repository = repository

    async def handle(self, query: GetMetricResultsQuery) -> list[MetricResult]:
        """Execute the get metric results query."""
        run_id = UUIDv7.from_string(query.run_id)
        return await self._repository.find_by_run_id(
            run_id,
            metric_name=query.metric_name,
        )


class GetAggregatedScoresHandler:
    """Handler for retrieving aggregated metric scores."""

    def __init__(self, repository: MetricResultRepository) -> None:
        """Initialize with repository."""
        self._repository = repository

    async def handle(
        self,
        query: GetAggregatedScoresQuery,
    ) -> dict[str, MetricAggregation]:
        """Execute the get aggregated scores query.

        Returns:
            Dictionary mapping metric names to their aggregations.

        """
        run_id = UUIDv7.from_string(query.run_id)
        results = await self._repository.find_by_run_id(
            run_id,
            metric_name=query.metric_name,
        )

        by_metric: dict[str, list[MetricResult]] = {}
        for r in results:
            by_metric.setdefault(r.metric_name, []).append(r)

        aggregations: dict[str, MetricAggregation] = {}
        for metric_name, metric_results in by_metric.items():
            aggregations[metric_name] = MetricAggregation.from_results(
                metric_name,
                tuple(metric_results),
            )

        return aggregations


class ListAvailableMetricsHandler:
    """Handler for listing available metrics."""

    def __init__(self, engine: MetricEngine) -> None:
        """Initialize with the metric engine."""
        self._engine = engine

    async def handle(
        self,
        query: ListAvailableMetricsQuery,
    ) -> list[MetricDefinition]:
        """Execute the list available metrics query."""
        if query.category:
            from app.evaluation.metrics.domain import MetricCategory

            try:
                cat = MetricCategory(query.category)
            except ValueError as exc:
                raise ValidationError(
                    message=f"Invalid category: {query.category}",
                    field="category",
                ) from exc
            return self._engine.list_by_category(cat)
        return self._engine.list_definitions()


class GetItemMetricResultsHandler:
    """Handler for retrieving metric results for a specific item."""

    def __init__(self, repository: MetricResultRepository) -> None:
        """Initialize with repository."""
        self._repository = repository

    async def handle(self, query: GetItemMetricResultsQuery) -> list[MetricResult]:
        """Execute the get item metric results query."""
        run_id = UUIDv7.from_string(query.run_id)
        item_id = UUIDv7.from_string(query.item_id)
        return await self._repository.find_by_item_id(run_id, item_id)
