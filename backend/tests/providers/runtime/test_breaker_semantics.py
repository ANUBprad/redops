"""R-12: provider runtime circuit-breaker semantics.

Proven defects in RuntimeCircuitBreaker + coordinator integration:
* ``failure_window_seconds`` is declared on CircuitBreakerConfig but never
  read, so unrelated failures accumulate forever until OPEN (cumulative,
  not windowed);
* the coordinator records EVERY invoke exception, so permanent caller
  errors (auth/model/context, retryable=False per R-02) trip the shared
  provider breaker and block subsequent valid requests.

Contract locked here:
* only failures inside the rolling window count toward the threshold;
  aged-out failures never open the breaker;
* explicitly non-retryable (fatal) errors never mutate the breaker;
* retryable failures count once per physical attempt;
* OPEN denies before invocation and breaks (never retries) the loop;
* local rate-limit denial and cancellation never mutate the breaker;
* OPEN rejection carries error_code CIRCUIT_BREAKER_OPEN, distinct from
  provider failure (""), local denial (RATE_LIMIT_EXCEEDED), timeout ("").

Classified separately (not fixed here): half_open_max_calls is unenforced,
so concurrent probes can all escape HALF_OPEN (in-process ceiling).

Fake handlers/clocks only -- no provider credentials involved.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.providers.exceptions.auth import AuthenticationRequired
from app.providers.exceptions.model import InvalidModel
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.runtime.circuit_breaker.runtime_circuit_breaker import (
    CircuitBreakerConfig,
    RuntimeCircuitBreaker,
    RuntimeCircuitState,
)
from app.providers.runtime.execution.runtime_coordinator import (
    ExecutionRequest,
    RuntimeCoordinator,
)
from app.providers.runtime.policies.runtime_policies import (
    ExecutionPolicy,
    RateLimitPolicy,
    RetryPolicy,
)


def _request(**overrides) -> ExecutionRequest:
    args = {
        "provider_name": "openai",
        "model_id": "gpt-4o",
        "request_id": "req-cb",
    }
    args.update(overrides)
    return ExecutionRequest(**args)


def _coordinator(
    failure_threshold: int = 5,
    max_attempts: int = 0,
    rate_limit: RateLimitPolicy | None = None,
) -> RuntimeCoordinator:
    coordinator = RuntimeCoordinator(
        ExecutionPolicy(
            retry=RetryPolicy(max_attempts=max_attempts, base_delay_seconds=0.01),
            rate_limit=rate_limit or RateLimitPolicy(),
        )
    )
    config = CircuitBreakerConfig(failure_threshold=failure_threshold)
    coordinator.get_circuit_breaker("openai", config)
    coordinator.get_circuit_breaker("anthropic", config)
    return coordinator


def test_failures_outside_window_age_out() -> None:
    breaker = RuntimeCircuitBreaker(
        CircuitBreakerConfig(failure_threshold=2, failure_window_seconds=0.15)
    )
    breaker.record_failure()
    time.sleep(0.2)
    breaker.record_failure()
    assert breaker.state == RuntimeCircuitState.CLOSED


def test_failures_inside_window_still_open() -> None:
    breaker = RuntimeCircuitBreaker(
        CircuitBreakerConfig(failure_threshold=2, failure_window_seconds=60.0)
    )
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == RuntimeCircuitState.OPEN


@pytest.mark.asyncio
async def test_fatal_errors_do_not_trip_breaker() -> None:
    coordinator = _coordinator(failure_threshold=2)
    calls = 0

    async def bad_key(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise AuthenticationRequired(message="bad key")

    async def bad_model(request: ExecutionRequest) -> str:
        raise InvalidModel(message="no such model", model_id="nope")

    for _ in range(3):
        assert (await coordinator.execute(_request(), bad_key)).success is False
    assert (await coordinator.execute(_request(), bad_model)).success is False
    assert calls == 3

    async def valid(request: ExecutionRequest) -> str:
        return "ok"

    result = await coordinator.execute(_request(), valid)
    assert result.success is True
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.CLOSED


@pytest.mark.asyncio
async def test_retryable_failures_count_per_physical_attempt() -> None:
    coordinator = _coordinator(failure_threshold=3, max_attempts=5)
    calls = 0

    async def always_429(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise RateLimitExceeded(message="slow down")

    result = await coordinator.execute(_request(), always_429)
    assert result.success is False
    # 3 admitted attempts trip the breaker; the 4th is denied before invocation.
    assert calls == 3
    assert "circuit breaker" in result.error.lower()
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.OPEN


@pytest.mark.asyncio
async def test_open_prevents_invocation_with_distinct_error_code() -> None:
    coordinator = _coordinator(failure_threshold=1)
    calls = 0

    async def fail(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise RateLimitExceeded(message="slow down")

    async def ok(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    await coordinator.execute(_request(), fail)
    blocked = await coordinator.execute(_request(), ok)
    assert blocked.success is False
    assert calls == 1
    assert blocked.telemetry.error_code == "CIRCUIT_BREAKER_OPEN"


@pytest.mark.asyncio
async def test_local_rate_denial_does_not_mutate_breaker() -> None:
    coordinator = _coordinator(
        failure_threshold=1,
        rate_limit=RateLimitPolicy(requests_per_minute=1),
    )
    coordinator.get_rate_limiter("openai").record_request("openai")
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        return "paid-call"

    denied = await coordinator.execute(_request(), handler)
    assert denied.success is False
    assert calls == 0
    assert denied.telemetry.error_code == "RATE_LIMIT_EXCEEDED"
    breaker = coordinator.get_circuit_breaker("openai")
    assert breaker.state == RuntimeCircuitState.CLOSED
    assert breaker.snapshot().failure_count == 0


@pytest.mark.asyncio
async def test_cancellation_does_not_mutate_breaker() -> None:
    coordinator = _coordinator(failure_threshold=1)

    async def slow(request: ExecutionRequest) -> str:
        await asyncio.sleep(30)
        return "too late"

    task = asyncio.create_task(coordinator.execute(_request(), slow))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    breaker = coordinator.get_circuit_breaker("openai")
    assert breaker.snapshot().failure_count == 0
    assert breaker.state == RuntimeCircuitState.CLOSED


@pytest.mark.asyncio
async def test_breaker_isolation_across_providers() -> None:
    coordinator = _coordinator(failure_threshold=1)

    async def fail(request: ExecutionRequest) -> str:
        raise RateLimitExceeded(message="slow down")

    async def ok(request: ExecutionRequest) -> str:
        return "ok"

    await coordinator.execute(_request(provider_name="openai"), fail)
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.OPEN
    result = await coordinator.execute(_request(provider_name="anthropic"), ok)
    assert result.success is True


@pytest.mark.asyncio
async def test_half_open_probe_success_closes_breaker() -> None:
    coordinator = RuntimeCoordinator(
        ExecutionPolicy(retry=RetryPolicy(max_attempts=0, base_delay_seconds=0.01))
    )
    coordinator.get_circuit_breaker(
        "openai",
        CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.05),
    )

    async def fail(request: ExecutionRequest) -> str:
        raise RateLimitExceeded(message="slow down")

    async def ok(request: ExecutionRequest) -> str:
        return "recovered"

    await coordinator.execute(_request(), fail)
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.OPEN
    await asyncio.sleep(0.08)
    result = await coordinator.execute(_request(), ok)
    assert result.success is True
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_probe_failure_reopens_breaker() -> None:
    coordinator = RuntimeCoordinator(
        ExecutionPolicy(retry=RetryPolicy(max_attempts=0, base_delay_seconds=0.01))
    )
    coordinator.get_circuit_breaker(
        "openai",
        CircuitBreakerConfig(failure_threshold=1, recovery_timeout_seconds=0.05),
    )

    async def fail(request: ExecutionRequest) -> str:
        raise RateLimitExceeded(message="slow down")

    await coordinator.execute(_request(), fail)
    await asyncio.sleep(0.08)
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.HALF_OPEN
    await coordinator.execute(_request(), fail)
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.OPEN
