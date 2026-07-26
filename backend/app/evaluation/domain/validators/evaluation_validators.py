"""Domain validation rules for the Evaluation engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.evaluation.domain.enums.evaluation_enums import EvaluationType, RunStatus
from app.evaluation.domain.state_machine.run_state_machine import RunStateMachine, TransitionContext
from app.kernel.exceptions.errors import ValidationError

if TYPE_CHECKING:
    from app.evaluation.domain.value_objects.evaluation_value_objects import (
        EvaluationConfiguration,
        EvaluationProfile,
        ExecutionBudget,
        ExecutionLimits,
        ExecutionPolicy,
    )

_MAX_TEMPERATURE: float = 2.0


class EvaluationValidator:
    """Validates EvaluationConfiguration invariants."""

    @staticmethod
    def validate(config: EvaluationConfiguration) -> list[ValidationError]:
        """Validate all evaluation configuration invariants."""
        errors: list[ValidationError] = []

        if not config.name or not config.name.strip():
            errors.append(ValidationError("Evaluation name is required", field="name"))
        if not config.metrics:
            errors.append(ValidationError("At least one metric is required", field="metrics"))

        dataset_required = {
            EvaluationType.DATASET,
            EvaluationType.REGRESSION,
            EvaluationType.SAFETY,
            EvaluationType.RAG,
            EvaluationType.COMPARISON,
        }
        if config.eval_type in dataset_required and config.dataset is None:
            msg = f"Evaluation type '{config.eval_type.value}' requires a dataset"
            errors.append(ValidationError(msg, field="dataset"))

        if config.dataset is not None:
            if not config.dataset.dataset_id:
                errors.append(
                    ValidationError("Dataset ID is required", field="dataset.dataset_id"),
                )
            if config.dataset.row_count < 0:
                errors.append(
                    ValidationError("Row count cannot be negative", field="dataset.row_count"),
                )

        errors.extend(EvaluationValidator._validate_profile(config.profile))
        errors.extend(EvaluationValidator._validate_budget(config.budget))
        errors.extend(EvaluationValidator._validate_limits(config.limits))
        errors.extend(EvaluationValidator._validate_policy(config.policy))
        return errors

    @staticmethod
    def validate_or_raise(config: EvaluationConfiguration) -> None:
        """Validate configuration and raise on first error."""
        errors = EvaluationValidator.validate(config)
        if errors:
            raise errors[0]

    @staticmethod
    def _validate_profile(profile: EvaluationProfile) -> list[ValidationError]:
        """Validate profile invariants."""
        errors: list[ValidationError] = []
        if not profile.provider_name:
            errors.append(
                ValidationError("Provider name is required", field="profile.provider_name"),
            )
        if not profile.model_id:
            errors.append(
                ValidationError("Model ID is required", field="profile.model_id"),
            )
        if not (0.0 <= profile.temperature <= _MAX_TEMPERATURE):
            errors.append(
                ValidationError(
                    "Temperature must be between 0.0 and 2.0",
                    field="profile.temperature",
                ),
            )
        if profile.max_tokens < 1:
            errors.append(
                ValidationError("Max tokens must be >= 1", field="profile.max_tokens"),
            )
        if profile.timeout_seconds <= 0:
            errors.append(
                ValidationError("Timeout must be positive", field="profile.timeout_seconds"),
            )
        return errors

    @staticmethod
    def _validate_budget(budget: ExecutionBudget) -> list[ValidationError]:
        """Validate budget invariants."""
        errors: list[ValidationError] = []
        if budget.max_cost_usd is not None and budget.max_cost_usd < 0:
            errors.append(
                ValidationError("Max cost cannot be negative", field="budget.max_cost_usd"),
            )
        if budget.max_tokens is not None and budget.max_tokens < 0:
            errors.append(
                ValidationError("Max tokens cannot be negative", field="budget.max_tokens"),
            )
        if budget.max_duration_seconds is not None and budget.max_duration_seconds <= 0:
            errors.append(
                ValidationError(
                    "Max duration must be positive",
                    field="budget.max_duration_seconds",
                ),
            )
        return errors

    @staticmethod
    def _validate_limits(limits: ExecutionLimits) -> list[ValidationError]:
        """Validate execution limits invariants."""
        errors: list[ValidationError] = []
        if limits.max_concurrency < 1:
            errors.append(
                ValidationError("Max concurrency must be >= 1", field="limits.max_concurrency"),
            )
        if limits.batch_size < 1:
            errors.append(
                ValidationError("Batch size must be >= 1", field="limits.batch_size"),
            )
        if limits.checkpoint_interval < 1:
            errors.append(
                ValidationError(
                    "Checkpoint interval must be >= 1",
                    field="limits.checkpoint_interval",
                ),
            )
        return errors

    @staticmethod
    def _validate_policy(policy: ExecutionPolicy) -> list[ValidationError]:
        """Validate execution policy invariants."""
        errors: list[ValidationError] = []
        if policy.max_retries_per_item < 0:
            errors.append(
                ValidationError(
                    "Max retries cannot be negative",
                    field="policy.max_retries_per_item",
                ),
            )
        if policy.timeout_per_item_seconds is not None and policy.timeout_per_item_seconds <= 0:
            errors.append(
                ValidationError(
                    "Per-item timeout must be positive",
                    field="policy.timeout_per_item_seconds",
                ),
            )
        return errors


class StateTransitionValidator:
    """Validates state transitions for evaluation runs."""

    def __init__(self) -> None:
        """Initialize with the run state machine."""
        self._state_machine = RunStateMachine()

    def validate(
        self,
        current_status: RunStatus,
        target: RunStatus,
        items_completed: int = 0,
        items_total: int = 0,
        has_checkpoint: bool = False,  # noqa: FBT001, FBT002
    ) -> list[ValidationError]:
        """Validate a state transition."""
        ctx = TransitionContext(
            items_completed=items_completed,
            items_total=items_total,
            has_checkpoint=has_checkpoint,
        )
        result = self._state_machine.transition(current_status, target, ctx)

        if result.success:
            return []

        error = result.error
        if error is not None:
            message = str(error)
        else:
            message = f"Invalid transition from {current_status.value} to {target.value}"
        return [
            ValidationError(
                message,
                field="status",
                details={
                    "current_status": current_status.value,
                    "target_status": target.value,
                },
            ),
        ]

    def validate_or_raise(
        self,
        current_status: RunStatus,
        target: RunStatus,
        items_completed: int = 0,
        items_total: int = 0,
        has_checkpoint: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Validate transition and raise on first error."""
        errors = self.validate(
            current_status,
            target,
            items_completed,
            items_total,
            has_checkpoint,
        )
        if errors:
            raise errors[0]
