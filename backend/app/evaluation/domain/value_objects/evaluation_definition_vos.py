"""Immutable value objects for the Evaluation definition aggregate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationName:
    """Validated name for an evaluation definition."""

    value: str

    def __post_init__(self) -> None:
        """Validate name invariants."""
        stripped = self.value.strip()
        if not stripped:
            msg = "Evaluation name cannot be empty"
            raise ValueError(msg)
        if len(stripped) > 255:
            msg = "Evaluation name cannot exceed 255 characters"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class EvaluationDescription:
    """Optional description for an evaluation definition."""

    value: str | None = None

    def __post_init__(self) -> None:
        """Validate description invariants."""
        if self.value is not None and len(self.value) > 2000:
            msg = "Evaluation description cannot exceed 2000 characters"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class MetricId:
    """Identifier for a metric used by an evaluation."""

    value: str

    def __post_init__(self) -> None:
        """Validate metric ID invariants."""
        stripped = self.value.strip()
        if not stripped:
            msg = "Metric ID cannot be empty"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ProviderId:
    """Identifier for an AI provider used by an evaluation."""

    value: str

    def __post_init__(self) -> None:
        """Validate provider ID invariants."""
        stripped = self.value.strip()
        if not stripped:
            msg = "Provider ID cannot be empty"
            raise ValueError(msg)
