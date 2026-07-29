"""Immutable telemetry models for provider runtime execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, unique


@unique
class CompletionStatus(Enum):
    """Execution completion status."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRY_EXHAUSTED = "retry_exhausted"
    FALLBACK_USED = "fallback_used"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"


@unique
class FailureCategory(Enum):
    """Categorized failure type."""

    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    CONTEXT_WINDOW = "context_window"
    PROVIDER_ERROR = "provider_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token usage breakdown."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0

    @property
    def has_usage(self) -> bool:
        """Return True if any tokens were used."""
        return self.total_tokens > 0


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Estimated cost for an execution."""

    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class LatencyMetrics:
    """Latency measurements."""

    total_ms: float = 0.0
    queue_ms: float = 0.0
    provider_ms: float = 0.0
    processing_ms: float = 0.0

    @property
    def overhead_ms(self) -> float:
        """Return runtime overhead (total minus provider time)."""
        return max(0.0, self.total_ms - self.provider_ms)


@dataclass(frozen=True, slots=True)
class RuntimeTelemetry:
    """Immutable telemetry snapshot for a single execution.

    Captures all observability data without infrastructure dependencies.

    Attributes:
        request_id: Unique execution identifier.
        provider_name: Provider that handled the request.
        model_id: Model used.
        status: Completion status.
        latency: Latency breakdown.
        tokens: Token usage.
        cost: Cost estimate.
        retry_count: Number of retries performed.
        fallback_count: Number of fallback attempts.
        circuit_breaker_state: Circuit breaker state at execution time.
        failure_category: Categorized failure if applicable.
        error_code: Error code if failed.
        error_message: Error message if failed.
        streaming_duration_ms: Duration of streaming response.
        timestamp: When this telemetry was captured.

    """

    request_id: str = ""
    provider_name: str = ""
    model_id: str = ""
    status: CompletionStatus = CompletionStatus.SUCCESS
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost: CostEstimate = field(default_factory=CostEstimate)
    retry_count: int = 0
    fallback_count: int = 0
    circuit_breaker_state: str = "closed"
    failure_category: FailureCategory | None = None
    error_code: str = ""
    error_message: str = ""
    streaming_duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_success(self) -> bool:
        """Return True if execution succeeded."""
        return self.status == CompletionStatus.SUCCESS

    @property
    def is_failure(self) -> bool:
        """Return True if execution failed."""
        return self.status == CompletionStatus.FAILED
