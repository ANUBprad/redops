"""Provider call accounting and cost/latency/token tracking.

Instruments the provider boundary to count calls and track resource
usage without invasive logging. Designed for regression detection:
if an evaluation suddenly makes more provider calls, this module
detects it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProviderCallRecord:
    """A single recorded provider call."""

    provider: str
    model: str
    call_type: str  # "target", "judge", "embedding"
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None


@dataclass
class ProviderCallCounter:
    """Accumulates provider calls during an evaluation.

    Thread-safe via GIL for CPython; sufficient for single-evaluation
    instrumentation.
    """

    target_calls: int = 0
    judge_calls: int = 0
    embedding_calls: int = 0
    total_calls: int = 0

    target_tokens_input: int = 0
    target_tokens_output: int = 0
    judge_tokens_input: int = 0
    judge_tokens_output: int = 0
    embedding_tokens_input: int = 0
    embedding_tokens_output: int = 0

    target_cost_usd: float = 0.0
    judge_cost_usd: float = 0.0
    embedding_cost_usd: float = 0.0

    target_latency_ms: int = 0
    judge_latency_ms: int = 0
    embedding_latency_ms: int = 0

    errors: int = 0
    records: list[ProviderCallRecord] = field(default_factory=list)

    def record(self, call: ProviderCallRecord) -> None:
        """Record a single provider call."""
        self.records.append(call)
        self.total_calls += 1

        if call.call_type == "target":
            self.target_calls += 1
            self.target_tokens_input += call.tokens_input
            self.target_tokens_output += call.tokens_output
            self.target_cost_usd += call.cost_usd
            self.target_latency_ms += call.latency_ms
        elif call.call_type == "judge":
            self.judge_calls += 1
            self.judge_tokens_input += call.tokens_input
            self.judge_tokens_output += call.tokens_output
            self.judge_cost_usd += call.cost_usd
            self.judge_latency_ms += call.latency_ms
        elif call.call_type == "embedding":
            self.embedding_calls += 1
            self.embedding_tokens_input += call.tokens_input
            self.embedding_tokens_output += call.tokens_output
            self.embedding_cost_usd += call.cost_usd
            self.embedding_latency_ms += call.latency_ms

        if call.error is not None:
            self.errors += 1

    @property
    def total_cost_usd(self) -> float:
        """Total cost across all call types."""
        return self.target_cost_usd + self.judge_cost_usd + self.embedding_cost_usd

    @property
    def total_tokens_input(self) -> int:
        """Total input tokens across all call types."""
        return self.target_tokens_input + self.judge_tokens_input + self.embedding_tokens_input

    @property
    def total_tokens_output(self) -> int:
        """Total output tokens across all call types."""
        return self.target_tokens_output + self.judge_tokens_output + self.embedding_tokens_output

    @property
    def total_latency_ms(self) -> int:
        """Total latency across all call types."""
        return self.target_latency_ms + self.judge_latency_ms + self.embedding_latency_ms

    def to_summary(self) -> dict[str, int | float]:
        """Produce a summary dictionary for reporting."""
        return {
            "target_calls": self.target_calls,
            "judge_calls": self.judge_calls,
            "embedding_calls": self.embedding_calls,
            "total_calls": self.total_calls,
            "target_tokens_input": self.target_tokens_input,
            "target_tokens_output": self.target_tokens_output,
            "judge_tokens_input": self.judge_tokens_input,
            "judge_tokens_output": self.judge_tokens_output,
            "embedding_tokens_input": self.embedding_tokens_input,
            "embedding_tokens_output": self.embedding_tokens_output,
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "target_cost_usd": self.target_cost_usd,
            "judge_cost_usd": self.judge_cost_usd,
            "embedding_cost_usd": self.embedding_cost_usd,
            "total_cost_usd": self.total_cost_usd,
            "target_latency_ms": self.target_latency_ms,
            "judge_latency_ms": self.judge_latency_ms,
            "embedding_latency_ms": self.embedding_latency_ms,
            "total_latency_ms": self.total_latency_ms,
            "errors": self.errors,
        }
