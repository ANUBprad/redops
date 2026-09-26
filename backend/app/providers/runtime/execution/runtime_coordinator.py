"""Coordinator — orchestrates all runtime components."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.providers.runtime.circuit_breaker.runtime_circuit_breaker import (
    CircuitBreakerConfig,
    RuntimeCircuitBreaker,
)
from app.providers.runtime.errors.runtime_errors import (
    CircuitBreakerOpenError,
    ExecutionTimeoutError,
    RateLimitExceededError,
)
from app.providers.runtime.fallback.fallback_chain import FallbackChain, FallbackEntry
from app.providers.runtime.middleware.middleware_pipeline import MiddlewareContext
from app.providers.runtime.policies.runtime_policies import (
    ExecutionPolicy,
    RateLimitPolicy,
    RetryPolicy,
)
from app.providers.runtime.rate_limit.rate_limiter import SlidingWindowRateLimiter
from app.providers.runtime.retry.retry_framework import RetryContext, RetryEvaluator
from app.providers.runtime.telemetry.runtime_telemetry import (
    CompletionStatus,
    FailureCategory,
    LatencyMetrics,
    RuntimeTelemetry,
    TokenUsage,
)

if TYPE_CHECKING:
    from app.providers.runtime.middleware.middleware_pipeline import (
        MiddlewarePipeline,
    )
    from app.providers.runtime.timeout.timeout_framework import TimeoutEvaluator


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Immutable execution request.

    Attributes:
        provider_name: Provider to call.
        model_id: Model to use.
        messages: Prompt messages.
        request_id: Unique identifier.
        budget_usd: Cost budget cap.
        timeout_seconds: Request timeout override.
        retry_policy: Retry policy override.
        metadata: Additional metadata.

    """

    provider_name: str = ""
    model_id: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)
    request_id: str = ""
    budget_usd: float = 0.0
    timeout_seconds: float = 0.0
    retry_policy: RetryPolicy | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeExecutionResult:
    """Immutable execution result from the runtime layer.

    Attributes:
        success: Whether execution succeeded.
        response: Response content.
        telemetry: Execution telemetry.
        error: Error message if failed.
        provider_used: Which provider ultimately handled request.
        model_used: Which model was used.

    """

    success: bool
    response: str = ""
    telemetry: RuntimeTelemetry = field(default_factory=RuntimeTelemetry)
    error: str = ""
    provider_used: str = ""
    model_used: str = ""


@dataclass
class RuntimeState:
    """Mutable runtime state."""

    circuit_breakers: dict[str, RuntimeCircuitBreaker] = field(default_factory=dict)
    rate_limiters: dict[str, SlidingWindowRateLimiter] = field(default_factory=dict)
    fallback_chains: dict[str, FallbackChain] = field(default_factory=dict)
    execution_count: int = 0
    total_cost_usd: float = 0.0


class RuntimeCoordinator:
    """Orchestrates retry, circuit breaker, rate limiting, fallback, and telemetry.

    Usage:
        coordinator = RuntimeCoordinator(policy)
        result = await coordinator.execute(request, handler)

    """

    def __init__(
        self,
        policy: ExecutionPolicy | None = None,
        pipeline: MiddlewarePipeline[Any, Any] | None = None,
    ) -> None:
        """Initialize coordinator."""
        self._policy = policy or ExecutionPolicy()
        self._pipeline = pipeline
        self._state = RuntimeState()
        self._timeout_evaluator: TimeoutEvaluator | None = None

    @property
    def total_cost_usd(self) -> float:
        """Return total cost across all executions."""
        return self._state.total_cost_usd

    @property
    def execution_count(self) -> int:
        """Return total execution count."""
        return self._state.execution_count

    def get_circuit_breaker(
        self,
        provider: str,
        config: CircuitBreakerConfig | None = None,
    ) -> RuntimeCircuitBreaker:
        """Get or create circuit breaker for provider."""
        if provider not in self._state.circuit_breakers:
            self._state.circuit_breakers[provider] = RuntimeCircuitBreaker(
                config or CircuitBreakerConfig(),
            )
        return self._state.circuit_breakers[provider]

    def get_rate_limiter(
        self,
        provider: str,
        policy: RateLimitPolicy | None = None,
    ) -> SlidingWindowRateLimiter:
        """Get or create rate limiter for provider (isolated per provider)."""
        if provider not in self._state.rate_limiters:
            self._state.rate_limiters[provider] = SlidingWindowRateLimiter(
                policy or self._policy.rate_limit,
            )
        return self._state.rate_limiters[provider]

    def configure_fallback(
        self,
        key: str,
        entries: list[FallbackEntry],
    ) -> None:
        """Configure fallback chain for a key."""
        self._state.fallback_chains[key] = FallbackChain(entries)

    def _get_timeout_evaluator(self) -> TimeoutEvaluator:
        """Get or create timeout evaluator (lazy)."""
        if self._timeout_evaluator is None:
            from app.providers.runtime.timeout.timeout_framework import (
                TimeoutEvaluator,
            )

            self._timeout_evaluator = TimeoutEvaluator(self._policy.timeout)
        return self._timeout_evaluator

    async def execute(
        self,
        request: ExecutionRequest,
        handler: Callable[[ExecutionRequest], Awaitable[Any]],
    ) -> RuntimeExecutionResult:
        """Execute a request through the runtime pipeline.

        Coordinates retry, circuit breaker, timeout, budget, and middleware.

        """
        start_time = datetime.now(UTC)
        self._state.execution_count += 1

        retry_policy = request.retry_policy or self._policy.retry
        retry_evaluator = RetryEvaluator(retry_policy)
        timeout_evaluator = self._get_timeout_evaluator()

        cb = self.get_circuit_breaker(request.provider_name)
        rate_limiter = self.get_rate_limiter(request.provider_name)
        enforce_rate_limit = self._policy.rate_limit.is_unlimited is False

        last_error: Exception | None = None
        local_rate_denial = False
        circuit_open_denial = False
        total_retries = 0
        cumulative_latency = 0.0

        for attempt in range(retry_policy.max_attempts + 1):
            attempt_start = datetime.now(UTC)

            timeout_result = timeout_evaluator.check(start_time)
            if timeout_result.is_expired:
                last_error = Exception(
                    f"Timeout exceeded: {timeout_result.elapsed_seconds:.1f}s",
                )
                break

            # Local rate-limit admission per physical attempt, before any
            # paid provider call. check()+record_request()+acquire run
            # back-to-back with no await between, so the pair is atomic
            # under the asyncio event loop. Denial consumes no quota,
            # touches no circuit breaker, and is never retried as a
            # provider call. Each admitted attempt consumes request quota
            # even if the provider call later fails or times out.
            # ponytail: in-memory per-process state only; multi-worker
            # deployments need a shared (Redis) limiter to enforce globally.
            concurrent_slot = False
            if enforce_rate_limit:
                admission = rate_limiter.check(request.provider_name)
                if not admission.allowed:
                    last_error = RateLimitExceededError(
                        f"Local rate limit exceeded for provider "
                        f"'{request.provider_name}' model '{request.model_id}' "
                        f"(limit {admission.limit}, "
                        f"retry after {admission.retry_after_seconds:.1f}s)",
                        retry_after_seconds=admission.retry_after_seconds,
                        details={
                            "provider_name": request.provider_name,
                            "model_id": request.model_id,
                        },
                    )
                    local_rate_denial = True
                    break
                if self._policy.rate_limit.concurrent_requests is not None and (
                    not rate_limiter.acquire_concurrent(request.provider_name)
                ):
                    last_error = RateLimitExceededError(
                        f"Local concurrency limit exceeded for provider "
                        f"'{request.provider_name}' model '{request.model_id}'",
                        details={
                            "provider_name": request.provider_name,
                            "model_id": request.model_id,
                        },
                    )
                    local_rate_denial = True
                    break
                rate_limiter.record_request(request.provider_name)
                concurrent_slot = self._policy.rate_limit.concurrent_requests is not None

            if not cb.can_execute():
                if concurrent_slot:
                    rate_limiter.release_concurrent(request.provider_name)
                last_error = CircuitBreakerOpenError(
                    message=f"Circuit breaker open for {request.provider_name}",
                )
                circuit_open_denial = True
                break

            async def _invoke() -> Any:
                if self._pipeline is not None:
                    ctx = MiddlewareContext(
                        provider_name=request.provider_name,
                        model_id=request.model_id,
                        request_id=request.request_id,
                    )
                    return await self._pipeline.execute(
                        request,
                        handler,
                        ctx,
                    )
                return await handler(request)

            try:
                timeout_seconds = request.timeout_seconds or 0.0
                if timeout_seconds > 0:
                    try:
                        async with asyncio.timeout(timeout_seconds):
                            response = await _invoke()
                    except TimeoutError as timeout_exc:
                        raise ExecutionTimeoutError(
                            f"Execution timed out after {timeout_seconds}s",
                            timeout_seconds=timeout_seconds,
                        ) from timeout_exc
                else:
                    response = await _invoke()

                cb.record_success()
                if concurrent_slot:
                    rate_limiter.release_concurrent(request.provider_name)

                attempt_latency = (datetime.now(UTC) - attempt_start).total_seconds() * 1000
                cumulative_latency += attempt_latency

                telemetry = RuntimeTelemetry(
                    request_id=request.request_id,
                    provider_name=request.provider_name,
                    model_id=request.model_id,
                    status=CompletionStatus.SUCCESS,
                    latency=LatencyMetrics(total_ms=cumulative_latency),
                    tokens=TokenUsage(),
                    retry_count=total_retries,
                )

                return RuntimeExecutionResult(
                    success=True,
                    response=str(response),
                    telemetry=telemetry,
                    provider_used=request.provider_name,
                    model_used=request.model_id,
                )

            except Exception as exc:
                last_error = exc
                if concurrent_slot:
                    rate_limiter.release_concurrent(request.provider_name)
                # Honor the exception taxonomy: explicitly non-retryable
                # errors (bad credentials, unknown model, over-limit
                # context) must never be re-POSTed as paid calls -- and
                # being caller/config problems rather than provider
                # distress, they must not trip the shared provider breaker.
                # Unclassified errors keep the legacy retry/count behavior.
                is_fatal = getattr(exc, "retryable", True) is False
                if not is_fatal:
                    cb.record_failure()
                attempt_latency = (datetime.now(UTC) - attempt_start).total_seconds() * 1000
                cumulative_latency += attempt_latency

                if is_fatal:
                    break

                retry_ctx = RetryContext(
                    attempt=attempt,
                    total_elapsed_seconds=(datetime.now(UTC) - start_time).total_seconds(),
                    last_error_code=getattr(exc, "error_code", ""),
                    last_error_message=str(exc),
                    consecutive_failures=attempt + 1,
                )
                decision = retry_evaluator.evaluate(retry_ctx)

                if not decision.should_retry:
                    break

                total_retries += 1
                await asyncio.sleep(decision.delay_seconds)
            except BaseException:
                # Cancellation (CancelledError) must propagate untouched;
                # just avoid leaking the concurrency slot.
                if concurrent_slot:
                    rate_limiter.release_concurrent(request.provider_name)
                raise

        return RuntimeExecutionResult(
            success=False,
            telemetry=RuntimeTelemetry(
                request_id=request.request_id,
                provider_name=request.provider_name,
                model_id=request.model_id,
                status=CompletionStatus.FAILED
                if local_rate_denial
                else (
                    CompletionStatus.RETRY_EXHAUSTED
                    if total_retries > 0
                    else CompletionStatus.FAILED
                ),
                latency=LatencyMetrics(total_ms=cumulative_latency),
                retry_count=total_retries,
                failure_category=(FailureCategory.RATE_LIMIT if local_rate_denial else None),
                error_code=(
                    "RATE_LIMIT_EXCEEDED"
                    if local_rate_denial
                    else ("CIRCUIT_BREAKER_OPEN" if circuit_open_denial else "")
                ),
                error_message=str(last_error),
            ),
            error=str(last_error),
            provider_used=request.provider_name,
            model_used=request.model_id,
        )
