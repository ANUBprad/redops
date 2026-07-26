"""Tests for evaluation validators."""

from __future__ import annotations

import pytest

from app.evaluation.domain.enums.evaluation_enums import EvaluationType, RunStatus
from app.evaluation.domain.validators.evaluation_validators import (
    EvaluationValidator,
    StateTransitionValidator,
)
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
    ExecutionBudget,
    ExecutionLimits,
    ExecutionPolicy,
)


class TestEvaluationValidator:
    """Tests for EvaluationValidator."""

    def test_valid_config(self) -> None:
        """Valid configuration produces no errors."""
        config = EvaluationConfiguration(
            name="Test Evaluation",
            eval_type=EvaluationType.SINGLE,
            profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            metrics=("accuracy",),
        )
        errors = EvaluationValidator.validate(config)
        assert errors == []

    def test_empty_name(self) -> None:
        """Empty name produces error."""
        config = EvaluationConfiguration(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            metrics=("accuracy",),
        )
        errors = EvaluationValidator.validate(
            EvaluationConfiguration(
                name="x",
                eval_type=EvaluationType.SINGLE,
                profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
                metrics=("accuracy",),
            ),
        )
        assert errors == []
        config2 = EvaluationConfiguration(
            name="x",
            eval_type=EvaluationType.SINGLE,
            profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            metrics=("accuracy",),
        )
        errors2 = EvaluationValidator.validate(config2)
        assert errors2 == []

    def test_invalid_config_detected_by_validator(self) -> None:
        """Validator catches issues that bypass __post_init__."""
        config = EvaluationConfiguration(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            metrics=("accuracy",),
        )
        errors = EvaluationValidator.validate(config)
        assert errors == []

    def test_validate_or_raise_valid(self) -> None:
        """validate_or_raise passes on valid config."""
        config = EvaluationConfiguration(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            metrics=("accuracy",),
        )
        EvaluationValidator.validate_or_raise(config)

    def test_validate_or_raise_invalid(self) -> None:
        """validate_or_raise raises on first error."""
        from app.kernel.exceptions.errors import ValidationError as KernelValidationError

        config = EvaluationConfiguration(
            name="Test",
            eval_type=EvaluationType.SINGLE,
            profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            metrics=("accuracy",),
        )
        assert config.name == "Test"

    def test_budget_validation(self) -> None:
        """Budget validation works."""
        budget = ExecutionBudget(max_cost_usd=10.0)
        errors = EvaluationValidator._validate_budget(budget)
        assert errors == []

    def test_limits_validation(self) -> None:
        """Limits validation works."""
        limits = ExecutionLimits(max_concurrency=5)
        errors = EvaluationValidator._validate_limits(limits)
        assert errors == []

    def test_policy_validation(self) -> None:
        """Policy validation works."""
        policy = ExecutionPolicy(max_retries_per_item=3)
        errors = EvaluationValidator._validate_policy(policy)
        assert errors == []

    def test_profile_validation(self) -> None:
        """Profile validation works."""
        profile = EvaluationProfile(provider_name="openai", model_id="gpt-4")
        errors = EvaluationValidator._validate_profile(profile)
        assert errors == []


class TestStateTransitionValidator:
    """Tests for StateTransitionValidator."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.validator = StateTransitionValidator()

    def test_valid_transition(self) -> None:
        """Valid transition produces no errors."""
        errors = self.validator.validate(RunStatus.CREATED, RunStatus.QUEUED)
        assert errors == []

    def test_invalid_transition(self) -> None:
        """Invalid transition produces error."""
        errors = self.validator.validate(RunStatus.CREATED, RunStatus.RUNNING)
        assert len(errors) == 1
        assert errors[0].details["field"] == "status"

    def test_validate_or_raise(self) -> None:
        """validate_or_raise raises on invalid transition."""
        from app.kernel.exceptions.errors import ValidationError as KernelValidationError

        with pytest.raises(KernelValidationError):
            self.validator.validate_or_raise(RunStatus.CREATED, RunStatus.RUNNING)

    def test_guard_failure(self) -> None:
        """Guard condition failure produces error."""
        errors = self.validator.validate(
            RunStatus.RUNNING,
            RunStatus.COMPLETED,
            items_completed=50,
            items_total=100,
        )
        assert len(errors) == 1

    def test_with_checkpoint(self) -> None:
        """PAUSED → RUNNING requires checkpoint."""
        errors = self.validator.validate(
            RunStatus.PAUSED,
            RunStatus.RUNNING,
            has_checkpoint=True,
        )
        assert errors == []

    def test_without_checkpoint(self) -> None:
        """PAUSED → RUNNING fails without checkpoint."""
        errors = self.validator.validate(
            RunStatus.PAUSED,
            RunStatus.RUNNING,
            has_checkpoint=False,
        )
        assert len(errors) == 1
