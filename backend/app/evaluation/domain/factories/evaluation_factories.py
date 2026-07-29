"""Factories for creating valid evaluation domain objects."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from app.evaluation.domain.entities.evaluation_entities import (
    AggregatedMetrics,
    EvaluationItem,
    EvaluationRun,
    ItemResult,
    RunCheckpoint,
)
from app.evaluation.domain.enums.evaluation_enums import EvaluationType, Priority
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    DatasetReference,
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionPolicy,
)
from app.kernel.exceptions.errors import ValidationError

if TYPE_CHECKING:
    from app.kernel.entities.base import UUIDv7

_ERROR_MESSAGES = {
    "name_required": "Evaluation name is required",
    "metrics_required": "At least one metric is required",
    "dataset_required": "Evaluation type '{type}' requires a dataset",
    "index_negative": "Item index cannot be negative: {index}",
    "checkpoint_number_negative": "Checkpoint number cannot be negative",
    "items_completed_negative": "Items completed cannot be negative",
    "items_total_negative": "Items total cannot be negative",
    "items_exceed_total": "Items completed cannot exceed items total",
    "last_index_invalid": "Last item index cannot be less than -1",
}

_DATASET_REQUIRED_TYPES: frozenset[EvaluationType] = frozenset(
    {
        EvaluationType.DATASET,
        EvaluationType.REGRESSION,
        EvaluationType.SAFETY,
        EvaluationType.RAG,
        EvaluationType.COMPARISON,
    }
)


class EvaluationConfigurationFactory:
    """Factory for creating validated EvaluationConfiguration instances."""

    @staticmethod
    def create(
        name: str,
        eval_type: EvaluationType,
        profile: EvaluationProfile,
        metrics: tuple[str, ...],
        dataset: DatasetReference | None = None,
        budget: ExecutionBudget | None = None,
        limits: ExecutionLimits | None = None,
        policy: ExecutionPolicy | None = None,
        priority: Priority = Priority.NORMAL,
    ) -> EvaluationConfiguration:
        """Create a validated EvaluationConfiguration."""
        if not name or not name.strip():
            raise ValidationError(_ERROR_MESSAGES["name_required"], field="name")
        if not metrics:
            raise ValidationError(_ERROR_MESSAGES["metrics_required"], field="metrics")
        if eval_type in _DATASET_REQUIRED_TYPES and dataset is None:
            msg = _ERROR_MESSAGES["dataset_required"].format(type=eval_type.value)
            raise ValidationError(msg, field="dataset")

        return EvaluationConfiguration(
            name=name.strip(),
            eval_type=eval_type,
            profile=profile,
            dataset=dataset,
            metrics=tuple(metrics),
            budget=budget or ExecutionBudget(),
            limits=limits or ExecutionLimits(),
            policy=policy or ExecutionPolicy(),
            priority=priority,
        )


class EvaluationRunFactory:
    """Factory for creating valid EvaluationRun instances."""

    @staticmethod
    def create(
        config: EvaluationConfiguration,
        profile: EvaluationProfile,
        metadata: EvaluationMetadata | None = None,
        entity_id: UUIDv7 | None = None,
    ) -> EvaluationRun:
        """Create a new EvaluationRun in CREATED state."""
        return EvaluationRun(
            evaluation_name=config.name,
            config=config,
            profile=profile,
            metadata=metadata or EvaluationMetadata(),
            entity_id=entity_id,
        )

    @staticmethod
    def create_queued(
        config: EvaluationConfiguration,
        profile: EvaluationProfile,
        metadata: EvaluationMetadata | None = None,
    ) -> EvaluationRun:
        """Create an EvaluationRun and transition it to QUEUED."""
        run = EvaluationRunFactory.create(config=config, profile=profile, metadata=metadata)
        run.queue()
        return run


class EvaluationItemFactory:
    """Factory for creating valid EvaluationItem instances."""

    @staticmethod
    def create(
        run_id: UUIDv7,
        index: int,
        data: dict[str, str | int | float | bool | None] | None = None,
        entity_id: UUIDv7 | None = None,
    ) -> EvaluationItem:
        """Create a new EvaluationItem."""
        if index < 0:
            msg = _ERROR_MESSAGES["index_negative"].format(index=index)
            raise ValidationError(msg, field="index")
        return EvaluationItem(run_id=run_id, index=index, data=data, entity_id=entity_id)


class RunCheckpointFactory:
    """Factory for creating valid RunCheckpoint instances."""

    @staticmethod
    def create(
        run_id: UUIDv7,
        checkpoint_number: int,
        items_completed: int,
        items_total: int,
        last_item_index: int,
        completed_item_ids: tuple[UUIDv7, ...] | None = None,
        accumulated_metrics: dict[str, list[float]] | None = None,
        accumulated_tokens_input: int = 0,
        accumulated_tokens_output: int = 0,
        accumulated_cost_usd: float = 0.0,
    ) -> RunCheckpoint:
        """Create a validated RunCheckpoint."""
        if checkpoint_number < 0:
            raise ValidationError(
                _ERROR_MESSAGES["checkpoint_number_negative"],
                field="checkpoint_number",
            )
        if items_completed < 0:
            raise ValidationError(
                _ERROR_MESSAGES["items_completed_negative"],
                field="items_completed",
            )
        if items_total < 0:
            raise ValidationError(
                _ERROR_MESSAGES["items_total_negative"],
                field="items_total",
            )
        if items_completed > items_total:
            raise ValidationError(
                _ERROR_MESSAGES["items_exceed_total"],
                field="items_completed",
            )
        if last_item_index < -1:
            raise ValidationError(
                _ERROR_MESSAGES["last_index_invalid"],
                field="last_item_index",
            )

        return RunCheckpoint(
            run_id=run_id,
            checkpoint_number=checkpoint_number,
            items_completed=items_completed,
            items_total=items_total,
            last_item_index=last_item_index,
            completed_item_ids=completed_item_ids or (),
            accumulated_metrics=accumulated_metrics or {},
            accumulated_tokens_input=accumulated_tokens_input,
            accumulated_tokens_output=accumulated_tokens_output,
            accumulated_cost_usd=accumulated_cost_usd,
        )


class AggregatedMetricsFactory:
    """Factory for creating AggregatedMetrics from item results."""

    @staticmethod
    def from_scores(
        metric_name: str,
        scores: list[float],
    ) -> AggregatedMetrics:
        """Create aggregated metrics from a list of scores."""
        return AggregatedMetrics.from_scores(metric_name, scores)

    @staticmethod
    def from_item_results(
        metric_name: str,
        item_results: tuple[ItemResult, ...],
    ) -> AggregatedMetrics:
        """Create aggregated metrics from item results."""
        scores = [
            result.scores[metric_name] for result in item_results if metric_name in result.scores
        ]
        total_items = len(item_results)
        computed_count = len(scores)
        partial = computed_count < total_items

        agg = AggregatedMetrics.from_scores(metric_name, scores)
        if partial:
            return replace(agg, partial=True)
        return agg
