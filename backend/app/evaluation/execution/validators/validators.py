"""Execution validators.

These validators enforce invariants on execution plans, pipelines,
dependencies, budgets, and concurrency settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.kernel.exceptions.errors import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.evaluation.domain.value_objects.evaluation_value_objects import (
        ExecutionBudget,
        ExecutionLimits,
    )
    from app.evaluation.execution.pipeline.plan import ExecutionPlan
    from app.evaluation.execution.pipeline.step import ExecutionStep
    from app.evaluation.execution.stages.types import StageType


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of a validation check."""

    valid: bool = True
    errors: tuple[str, ...] = ()

    @classmethod
    def ok(cls) -> ValidationResult:
        """Return a successful validation result."""
        return cls(valid=True)

    @classmethod
    def failed(cls, *errors: str) -> ValidationResult:
        """Return a failed validation result with errors."""
        return cls(valid=False, errors=errors)


class PlanValidator:
    """Validates an ExecutionPlan for structural correctness."""

    @staticmethod
    def validate(plan: ExecutionPlan) -> ValidationResult:
        """Validate the structure of an execution plan.

        Args:
            plan: The plan to validate.

        Returns:
            A ValidationResult indicating validity.

        """
        errors: list[str] = []

        if len(plan.steps) == 0:
            errors.append("Plan must contain at least one step")

        if len(plan.stages) == 0:
            errors.append("Plan must contain at least one stage")

        stage_types_in_plan = {step.stage_type for step in plan.steps}
        if stage_types_in_plan - set(plan.stages):
            errors.append("Plan has steps referencing stages not declared in the plan")

        if plan.total_items < 0:
            errors.append("Total items cannot be negative")

        seen_step_ids = {step.step_id for step in plan.steps}
        if len(seen_step_ids) != len(plan.steps):
            errors.append("Duplicate step IDs detected in plan")

        return ValidationResult.failed(*errors) if errors else ValidationResult.ok()

    @staticmethod
    def validate_or_raise(plan: ExecutionPlan) -> None:
        """Validate and raise on the first error.

        Args:
            plan: The plan to validate.

        Raises:
            ValidationError: If the plan is invalid.

        """
        result = PlanValidator.validate(plan)
        if not result.valid:
            msg = result.errors[0] if result.errors else "Unknown plan validation error"
            raise ValidationError(msg, field="execution_plan")


class DependencyGraphValidator:
    """Validates the step dependency graph for correctness.

    Detects circular dependencies, missing dependencies, and
    ensures the dependency DAG is well-formed.
    """

    @staticmethod
    def validate(steps: Sequence[ExecutionStep]) -> ValidationResult:
        """Validate the step dependency graph.

        Args:
            steps: The list of steps with their dependencies.

        Returns:
            A ValidationResult indicating validity.

        """
        errors: list[str] = []
        step_ids = {step.step_id for step in steps}

        # Check for missing dependencies
        for step in steps:
            for dep in step.dependencies:
                if dep.step_id not in step_ids:
                    errors.append(
                        f"Step {step.step_id} depends on missing step {dep.step_id}",
                    )

        # Check for circular dependencies using DFS
        adjacency: dict[str, list[str]] = {}
        for step in steps:
            sid = str(step.step_id)
            adjacency[sid] = [str(d.step_id) for d in step.dependencies]

        visited: set[str] = set()
        in_stack: set[str] = set()

        def _has_cycle(node: str, path: list[str]) -> str | None:
            """DFS cycle detection."""
            visited.add(node)
            in_stack.add(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    result = _has_cycle(neighbor, path + [neighbor])
                    if result is not None:
                        return result
                elif neighbor in in_stack:
                    cycle_path = " -> ".join(path + [neighbor])
                    return f"Circular dependency detected: {cycle_path}"
            in_stack.discard(node)
            return None

        for step in steps:
            sid = str(step.step_id)
            if sid not in visited:
                cycle = _has_cycle(sid, [sid])
                if cycle is not None:
                    errors.append(cycle)

        return ValidationResult.failed(*errors) if errors else ValidationResult.ok()

    @staticmethod
    def validate_or_raise(steps: Sequence[ExecutionStep]) -> None:
        """Validate and raise on the first error.

        Args:
            steps: The list of steps to validate.

        Raises:
            ValidationError: If dependency validation fails.

        """
        result = DependencyGraphValidator.validate(steps)
        if not result.valid:
            msg = result.errors[0] if result.errors else "Unknown dependency error"
            raise ValidationError(msg, field="step_dependencies")


class BudgetValidator:
    """Validates execution budget parameters."""

    @staticmethod
    def validate(budget: ExecutionBudget | None, total_items: int = 0) -> ValidationResult:
        """Validate budget parameters.

        Args:
            budget: The budget to validate.
            total_items: Item count for per-item budget checks.

        Returns:
            A ValidationResult indicating validity.

        """
        errors: list[str] = []

        if budget is None:
            return ValidationResult.ok()

        if budget.max_cost_usd is not None and budget.max_cost_usd < 0:
            errors.append("Max cost cannot be negative")
        if budget.max_tokens is not None and budget.max_tokens < 0:
            errors.append("Max tokens cannot be negative")
        if budget.max_duration_seconds is not None and budget.max_duration_seconds <= 0:
            errors.append("Max duration must be positive")

        if total_items > 0 and budget.max_cost_usd is not None and budget.max_cost_usd == 0:
            errors.append("Max cost cannot be zero when items are present")

        return ValidationResult.failed(*errors) if errors else ValidationResult.ok()

    @staticmethod
    def validate_or_raise(
        budget: ExecutionBudget | None,
        total_items: int = 0,
    ) -> None:
        """Validate and raise on the first error.

        Args:
            budget: The budget to validate.
            total_items: Optional item count.

        Raises:
            ValidationError: If budget validation fails.

        """
        result = BudgetValidator.validate(budget, total_items)
        if not result.valid:
            msg = result.errors[0] if result.errors else "Unknown budget error"
            raise ValidationError(msg, field="execution_budget")


class ConcurrencyValidator:
    """Validates concurrency and limits configuration."""

    @staticmethod
    def validate(limits: ExecutionLimits | None, total_items: int = 0) -> ValidationResult:
        """Validate concurrency and limits.

        Args:
            limits: The limits to validate.
            total_items: Item count for concurrency checks.

        Returns:
            A ValidationResult indicating validity.

        """
        errors: list[str] = []

        if limits is None:
            return ValidationResult.ok()

        if limits.max_concurrency < 1:
            errors.append("Max concurrency must be >= 1")
        if limits.batch_size < 1:
            errors.append("Batch size must be >= 1")
        if limits.checkpoint_interval < 1:
            errors.append("Checkpoint interval must be >= 1")

        if total_items > 0 and limits.max_concurrency > total_items:
            errors.append(
                f"Max concurrency ({limits.max_concurrency}) exceeds total items ({total_items})",
            )

        if limits.max_concurrency > limits.batch_size:
            errors.append(
                f"Max concurrency ({limits.max_concurrency}) exceeds batch size ({limits.batch_size})",
            )

        return ValidationResult.failed(*errors) if errors else ValidationResult.ok()

    @staticmethod
    def validate_or_raise(limits: ExecutionLimits | None, total_items: int = 0) -> None:
        """Validate and raise on the first error.

        Args:
            limits: The limits to validate.
            total_items: Optional item count.

        Raises:
            ValidationError: If concurrency validation fails.

        """
        result = ConcurrencyValidator.validate(limits, total_items)
        if not result.valid:
            msg = result.errors[0] if result.errors else "Unknown concurrency error"
            raise ValidationError(msg, field="execution_limits")


class StageOrderingValidator:
    """Validates that stages are in the correct canonical order."""

    @staticmethod
    def validate(stages: Sequence[StageType]) -> ValidationResult:
        """Validate stage ordering.

        Args:
            stages: The ordered list of stage types.

        Returns:
            A ValidationResult indicating validity.

        """
        errors: list[str] = []

        if not stages:
            return ValidationResult.failed("Stage list cannot be empty")

        # Check for duplicates
        if len(stages) != len(set(stages)):
            errors.append("Duplicate stages detected")

        # Check canonical ordering
        for i in range(len(stages) - 1):
            if stages[i].order >= stages[i + 1].order:
                errors.append(
                    f"Stage {stages[i].value} (order {stages[i].order}) "
                    f"must come before {stages[i + 1].value} (order {stages[i + 1].order})",
                )

        return ValidationResult.failed(*errors) if errors else ValidationResult.ok()

    @staticmethod
    def validate_or_raise(stages: Sequence[StageType]) -> None:
        """Validate and raise on the first error.

        Args:
            stages: The ordered list of stage types.

        Raises:
            ValidationError: If stage ordering is invalid.

        """
        result = StageOrderingValidator.validate(stages)
        if not result.valid:
            msg = result.errors[0] if result.errors else "Unknown stage ordering error"
            raise ValidationError(msg, field="stage_ordering")
