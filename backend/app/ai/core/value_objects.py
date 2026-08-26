"""Unified AI execution value objects.

Shared immutable value objects for budget, metadata, and provider
configuration used across evaluation, agent runtime, and red team.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    """Budget constraints for an AI execution run.

    Shared across evaluation runs and agent runs.
    """

    max_cost_usd: float | None = None
    max_tokens: int | None = None
    max_duration_seconds: int | None = None

    def __post_init__(self) -> None:
        """Validate budget invariants."""
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            msg = "Max cost cannot be negative"
            raise ValueError(msg)
        if self.max_tokens is not None and self.max_tokens < 0:
            msg = "Max tokens cannot be negative"
            raise ValueError(msg)
        if self.max_duration_seconds is not None and self.max_duration_seconds <= 0:
            msg = "Max duration must be positive"
            raise ValueError(msg)

    @property
    def is_unlimited(self) -> bool:
        """Return True if all budget dimensions are unlimited."""
        return (
            self.max_cost_usd is None
            and self.max_tokens is None
            and self.max_duration_seconds is None
        )


@dataclass(frozen=True, slots=True)
class ExecutionMetadata:
    """Metadata associated with an AI execution run.

    Shared across evaluation runs and agent runs.
    """

    project_id: str | None = None
    created_by: str | None = None
    tags: tuple[str, ...] = ()
    description: str | None = None
    judge_provider: str | None = None
    judge_model: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderProfile:
    """Resolved provider and model configuration.

    Shared across evaluation runs and agent runs.
    """

    provider_name: str = ""
    model_id: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_seconds: int = 60
    system_prompt: str | None = None
