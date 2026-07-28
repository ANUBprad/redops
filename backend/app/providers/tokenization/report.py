"""Usage report.

Aggregates token usage and cost data across multiple
requests for reporting and budgeting purposes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class UsageReport:
    """Aggregated usage report across multiple operations.

    Provides summary statistics for token consumption and
    estimated costs for budget tracking.
    """

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_audio_tokens: int = 0
    total_requests: int = 0
    total_cost_usd: float = 0.0
    provider_breakdown: dict[str, int] = field(default_factory=dict)
    model_breakdown: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Return total tokens across all requests."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def average_input_tokens(self) -> float:
        """Return average input tokens per request."""
        if self.total_requests == 0:
            return 0.0
        return self.total_input_tokens / self.total_requests

    @property
    def average_output_tokens(self) -> float:
        """Return average output tokens per request."""
        if self.total_requests == 0:
            return 0.0
        return self.total_output_tokens / self.total_requests

    @property
    def cache_hit_ratio(self) -> float:
        """Return the ratio of cached to total input tokens."""
        if self.total_input_tokens == 0:
            return 0.0
        return self.total_cached_tokens / self.total_input_tokens

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"UsageReport(requests={self.total_requests}, "
            f"tokens={self.total_tokens}, "
            f"cost=${self.total_cost_usd:.4f})"
        )
