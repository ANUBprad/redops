"""Runtime policy objects — immutable, composable configurations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique

# ── Retry Policy ──────────────────────────────────────────────────────


@unique
class BackoffStrategy(Enum):
    """Backoff strategy for retry delays."""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Immutable retry configuration.

    Attributes:
        max_attempts: Maximum number of retry attempts (0 = no retry).
        backoff_strategy: Backoff strategy.
        base_delay_seconds: Base delay between retries.
        max_delay_seconds: Maximum delay cap.
        jitter: Whether to add random jitter to delays.
        retryable_error_codes: Error codes eligible for retry.
        total_retry_budget_seconds: Maximum total time spent retrying.

    """

    max_attempts: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    jitter: bool = True
    retryable_error_codes: tuple[str, ...] = ()
    total_retry_budget_seconds: float = 120.0

    @property
    def is_enabled(self) -> bool:
        """Return True if retries are enabled."""
        return self.max_attempts > 0

    def delay_for_attempt(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (0-indexed)."""
        if self.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.base_delay_seconds
        elif self.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.base_delay_seconds * (attempt + 1)
        else:
            delay = self.base_delay_seconds * (2.0**attempt)
        return min(delay, self.max_delay_seconds)


# ── Timeout Policy ────────────────────────────────────────────────────


@unique
class TimeoutType(Enum):
    """Type of timeout."""

    SOFT = "soft"
    HARD = "hard"


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    """Immutable timeout configuration.

    Attributes:
        request_timeout_seconds: Per-request timeout.
        provider_timeout_seconds: Per-provider timeout.
        global_deadline_seconds: Global deadline for entire execution.
        timeout_type: Whether timeout is soft (cancellable) or hard (forced).

    """

    request_timeout_seconds: float = 60.0
    provider_timeout_seconds: float = 300.0
    global_deadline_seconds: float | None = None
    timeout_type: TimeoutType = TimeoutType.SOFT

    @property
    def effective_timeout(self) -> float:
        """Return the effective timeout (shortest of configured)."""
        candidates = [
            self.request_timeout_seconds,
            self.provider_timeout_seconds,
        ]
        if self.global_deadline_seconds is not None:
            candidates.append(self.global_deadline_seconds)
        return min(candidates)


# ── Fallback Policy ───────────────────────────────────────────────────


@unique
class FallbackTarget(Enum):
    """Fallback target scope."""

    PROVIDER = "provider"
    MODEL = "model"
    REGION = "region"


@dataclass(frozen=True, slots=True)
class FallbackEntry:
    """Single fallback target."""

    provider_name: str
    model_id: str = ""
    priority: int = 0


@dataclass(frozen=True, slots=True)
class FallbackPolicy:
    """Immutable fallback configuration.

    Attributes:
        enabled: Whether fallback is enabled.
        strategy: Fallback strategy.
        fallback_chain: Ordered list of fallback targets.
        max_fallback_attempts: Maximum fallback attempts.

    """

    enabled: bool = True
    strategy: FallbackTarget = FallbackTarget.PROVIDER
    fallback_chain: tuple[FallbackEntry, ...] = ()
    max_fallback_attempts: int = 3


# ── Rate Limit Policy ─────────────────────────────────────────────────


@unique
class RateLimitAlgorithm(Enum):
    """Rate limiting algorithm."""

    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """Immutable rate limit configuration.

    Attributes:
        requests_per_minute: Maximum requests per minute.
        tokens_per_minute: Maximum tokens per minute.
        concurrent_requests: Maximum concurrent requests.
        burst_capacity: Maximum burst size.
        algorithm: Rate limiting algorithm.

    """

    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None
    concurrent_requests: int | None = None
    burst_capacity: int | None = None
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW

    @property
    def is_unlimited(self) -> bool:
        """Return True if no rate limits are configured."""
        return (
            self.requests_per_minute is None
            and self.tokens_per_minute is None
            and self.concurrent_requests is None
        )


# ── Caching Policy ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CachingPolicy:
    """Immutable caching configuration.

    Attributes:
        enabled: Whether caching is enabled.
        ttl_seconds: Time-to-live for cached responses.
        max_cache_size: Maximum number of cached entries.
        cache_key_prefix: Prefix for cache keys.
        cache_identical_requests: Whether to cache identical requests.

    """

    enabled: bool = False
    ttl_seconds: float = 300.0
    max_cache_size: int = 1000
    cache_key_prefix: str = "runtime"
    cache_identical_requests: bool = True


# ── Telemetry Policy ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TelemetryPolicy:
    """Immutable telemetry configuration.

    Attributes:
        enabled: Whether telemetry is enabled.
        capture_latency: Capture latency metrics.
        capture_tokens: Capture token usage metrics.
        capture_cost: Capture cost estimates.
        capture_errors: Capture error details.
        sample_rate: Sampling rate (0.0 to 1.0).

    """

    enabled: bool = True
    capture_latency: bool = True
    capture_tokens: bool = True
    capture_cost: bool = True
    capture_errors: bool = True
    sample_rate: float = 1.0


# ── Execution Policy (Composite) ─────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Composite execution policy combining all sub-policies.

    Attributes:
        retry: Retry configuration.
        timeout: Timeout configuration.
        fallback: Fallback configuration.
        rate_limit: Rate limit configuration.
        caching: Caching configuration.
        telemetry: Telemetry configuration.

    """

    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    fallback: FallbackPolicy = field(default_factory=FallbackPolicy)
    rate_limit: RateLimitPolicy = field(default_factory=RateLimitPolicy)
    caching: CachingPolicy = field(default_factory=CachingPolicy)
    telemetry: TelemetryPolicy = field(default_factory=TelemetryPolicy)
