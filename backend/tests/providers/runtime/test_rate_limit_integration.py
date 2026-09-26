"""R-04: provider runtime rate-limiter integration.

Proven defect: RuntimeCoordinator declared ``rate_limiters`` state but never
consulted SlidingWindowRateLimiter, so any request/model policy (e.g. rpm=1)
still executed every paid provider call.

Contract locked here (from current limiter/policy source, not invented):
* admission is checked per physical provider attempt, before invocation;
* each admitted attempt consumes one request quota even if the provider call
  later fails or times out; local denial consumes none;
* local denial touches no circuit breaker and is never retried as a call;
* isolation key is the provider name; no model-level convention exists;
* the limiter enforces requests_per_minute (+ concurrent_requests) only --
  tokens_per_minute/burst_capacity/algorithm are declared on RateLimitPolicy
  but unread by SlidingWindowRateLimiter (known gap, pinned below).

Fake handlers only -- no provider credentials involved.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.providers.exceptions.auth import AuthenticationRequired
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.runtime.execution.runtime_coordinator import (
    ExecutionRequest,
    RuntimeCoordinator,
)
from app.providers.runtime.policies.runtime_policies import (
    ExecutionPolicy,
    RateLimitPolicy,
    RetryPolicy,
)
from app.providers.runtime.telemetry.runtime_telemetry import FailureCategory


def _request(**overrides) -> ExecutionRequest:
    args = {
        "provider_name": "openai",
        "model_id": "gpt-4o",
        "request_id": "req-rl",
    }
    args.update(overrides)
    return ExecutionRequest(**args)


def _policy(
    rate_limit: RateLimitPolicy,
    max_attempts: int = 0,
) -> ExecutionPolicy:
    return ExecutionPolicy(
        retry=RetryPolicy(max_attempts=max_attempts, base_delay_seconds=0.01),
        rate_limit=rate_limit,
    )


def _usage(coordinator: RuntimeCoordinator, provider: str = "openai") -> int:
    timestamps = coordinator.get_rate_limiter(provider)._request_timestamps.get(provider)
    return 0 if timestamps is None else len(timestamps)


@pytest.mark.asyncio
async def test_under_limit_request_executes_normally() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=5)))
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await coordinator.execute(_request(), handler)
    assert result.success is True
    assert result.response == "ok"
    assert calls == 1


@pytest.mark.asyncio
async def test_exhausted_request_limit_prevents_provider_invocation() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=1)))
    coordinator.get_rate_limiter("openai").record_request("openai")
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        return "paid-call"

    result = await coordinator.execute(_request(), handler)
    assert result.success is False
    assert calls == 0
    assert "Local rate limit" in result.error
    assert result.telemetry.error_code == "RATE_LIMIT_EXCEEDED"
    assert result.telemetry.failure_category is FailureCategory.RATE_LIMIT


@pytest.mark.asyncio
async def test_token_policy_not_enforced_documents_contract_gap() -> None:
    """tokens_per_minute is declared but unread by the limiter: no gating.

    Pinned so nobody silently assumes token enforcement exists; adding it
    is a separate feature (estimator wiring + policy semantics), not R-04.
    """
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(tokens_per_minute=1)))
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await coordinator.execute(_request(), handler)
    assert result.success is True
    assert calls == 1


@pytest.mark.asyncio
async def test_successful_call_records_expected_usage() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=5)))

    async def handler(request: ExecutionRequest) -> str:
        return "ok"

    assert _usage(coordinator) == 0
    assert (await coordinator.execute(_request(), handler)).success is True
    assert _usage(coordinator) == 1
    assert (await coordinator.execute(_request(), handler)).success is True
    assert _usage(coordinator) == 2


@pytest.mark.asyncio
async def test_fatal_failure_preserves_no_retry_and_consumes_quota() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=5)))
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise AuthenticationRequired(message="bad key")

    result = await coordinator.execute(_request(), handler)
    assert result.success is False
    assert calls == 1
    assert _usage(coordinator) == 1


@pytest.mark.asyncio
async def test_retryable_failure_retries_and_each_attempt_consumes_quota() -> None:
    coordinator = RuntimeCoordinator(
        _policy(RateLimitPolicy(requests_per_minute=5), max_attempts=3)
    )
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitExceeded(message="slow down")
        return "recovered"

    result = await coordinator.execute(_request(), handler)
    assert result.success is True
    assert calls == 2
    assert _usage(coordinator) == 2


@pytest.mark.asyncio
async def test_timeout_preserves_bounded_execution() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=5)))

    async def slow(request: ExecutionRequest) -> str:
        await asyncio.sleep(30)
        return "too late"

    started = time.monotonic()
    result = await coordinator.execute(_request(timeout_seconds=0.2), slow)
    elapsed = time.monotonic() - started
    assert result.success is False
    assert "timed out" in result.error.lower()
    assert elapsed < 10
    assert _usage(coordinator) == 1


@pytest.mark.asyncio
async def test_mid_retry_exhaustion_denies_locally_without_further_calls() -> None:
    coordinator = RuntimeCoordinator(
        _policy(RateLimitPolicy(requests_per_minute=2), max_attempts=5)
    )
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise RateLimitExceeded(message="slow down")

    result = await coordinator.execute(_request(), handler)
    assert result.success is False
    assert calls == 2
    assert "Local rate limit" in result.error
    assert result.telemetry.error_code == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_provider_policy_isolation() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=1)))
    coordinator.get_rate_limiter("openai").record_request("openai")
    calls: list[str] = []

    async def handler(request: ExecutionRequest) -> str:
        calls.append(request.provider_name)
        return "ok"

    denied = await coordinator.execute(_request(provider_name="openai"), handler)
    allowed = await coordinator.execute(_request(provider_name="anthropic"), handler)
    assert denied.success is False
    assert allowed.success is True
    assert calls == ["anthropic"]


@pytest.mark.asyncio
async def test_concurrent_requests_share_one_window_atomically() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=3)))

    async def handler(request: ExecutionRequest) -> str:
        return "ok"

    results = await asyncio.gather(
        *(coordinator.execute(_request(request_id=f"r{i}"), handler) for i in range(5))
    )
    assert sum(1 for r in results if r.success) == 3
    assert sum(1 for r in results if not r.success) == 2
    assert _usage(coordinator) == 3


@pytest.mark.asyncio
async def test_denial_distinguishable_from_provider_timeout_circuit_fatal() -> None:
    from app.providers.runtime.circuit_breaker.runtime_circuit_breaker import (
        CircuitBreakerConfig,
    )

    async def ok(request: ExecutionRequest) -> str:
        return "ok"

    async def provider_429(request: ExecutionRequest) -> str:
        raise RateLimitExceeded(message="provider slow down")

    async def fatal(request: ExecutionRequest) -> str:
        raise AuthenticationRequired(message="bad key")

    limited = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=1)))
    limited.get_rate_limiter("openai").record_request("openai")
    denial = await limited.execute(_request(), ok)
    assert "Local rate limit" in denial.error
    assert denial.telemetry.error_code == "RATE_LIMIT_EXCEEDED"
    assert denial.telemetry.failure_category is FailureCategory.RATE_LIMIT

    plain = RuntimeCoordinator(_policy(RateLimitPolicy(), max_attempts=0))
    provider_denied = await plain.execute(_request(), provider_429)
    assert provider_denied.success is False
    assert "Local rate limit" not in provider_denied.error
    assert provider_denied.telemetry.error_code == ""
    assert provider_denied.telemetry.failure_category is None

    async def slow(request: ExecutionRequest) -> str:
        await asyncio.sleep(30)
        return "late"

    timeout = await plain.execute(_request(timeout_seconds=0.1), slow)
    assert "timed out" in timeout.error.lower()
    assert timeout.telemetry.error_code == ""

    breaking = RuntimeCoordinator(_policy(RateLimitPolicy(), max_attempts=0))
    breaking.get_circuit_breaker("openai", CircuitBreakerConfig(failure_threshold=1))
    await breaking.execute(_request(), fatal)
    circuit_open = await breaking.execute(_request(), ok)
    assert "circuit breaker" in circuit_open.error.lower()
    assert circuit_open.telemetry.error_code == ""

    fatal_result = await plain.execute(_request(), fatal)
    assert fatal_result.success is False
    assert fatal_result.telemetry.error_code == ""


def test_rate_limiter_singleton_per_provider() -> None:
    coordinator = RuntimeCoordinator(_policy(RateLimitPolicy(requests_per_minute=2)))
    assert coordinator.get_rate_limiter("openai") is coordinator.get_rate_limiter("openai")
    assert coordinator.get_rate_limiter("openai") is not coordinator.get_rate_limiter("anthropic")


@pytest.mark.asyncio
async def test_unlimited_default_preserves_legacy_behavior() -> None:
    coordinator = RuntimeCoordinator()
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    for _ in range(3):
        assert (await coordinator.execute(_request(), handler)).success is True
    assert calls == 3
    assert coordinator._state.rate_limiters["openai"].check("openai").allowed is True
