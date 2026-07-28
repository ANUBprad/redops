"""Token usage data model.

Tracks token consumption for a single request or aggregation
across multiple requests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage for a single operation.

    Immutable record of token consumption. Supports aggregation
    via the add() method which returns a new instance.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    audio_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Return total tokens consumed."""
        return self.input_tokens + self.output_tokens

    @property
    def billable_tokens(self) -> int:
        """Return tokens subject to billing (excludes cached)."""
        return self.input_tokens + self.output_tokens - self.cached_tokens

    def add(self, other: TokenUsage) -> TokenUsage:
        """Create a new usage instance with combined totals.

        Args:
            other: The other usage to combine with.

        Returns:
            A new TokenUsage with summed values.

        """
        merged_metadata = {**self.metadata, **other.metadata}
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            audio_tokens=self.audio_tokens + other.audio_tokens,
            metadata=merged_metadata,
        )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"TokenUsage(input={self.input_tokens}, "
            f"output={self.output_tokens}, "
            f"total={self.total_tokens})"
        )
