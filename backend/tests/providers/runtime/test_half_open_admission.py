"""R-12B: circuit-breaker HALF_OPEN admission correctness.

Proven defect: ``half_open_max_calls`` had zero readers, so 5/5
concurrent HALF_OPEN probes invoked the provider with max=1.

Contract locked here (from current source, not textbooks):
* the cap limits SIMULTANEOUS in-flight probes (a total-per-episode cap
  would deadlock success_threshold > max_calls);
* admission reserves synchronously inside acquire() (atomic in the loop);
* every transition starts a new generation; stale completions are
  ignored so late probes cannot corrupt a newer episode;
* each coordinator attempt re-admits (per-physical-attempt, like R-12
  accounting); a failed probe reopens, denying further retries;
* breaker admission precedes rate-limit admission: zero-call denials
  consume neither quota nor breaker accounting;
* exhausted-capacity rejection reuses CIRCUIT_BREAKER_OPEN with a
  half-open-specific message; zero provider calls.

Fake handlers/Event barriers only -- no live providers, no sleep-races
(the single recovery sleep is one-sided: longer than the timeout).
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.providers.exceptions.auth import AuthenticationRequired
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
        "request_id": "req-half-open",
    }
    args.update(overrides)
    return ExecutionRequest(**args)


def _coordinator(
    failure_threshold: int = 1,
    recovery_timeout_seconds: float = 0.05,
    half_open_max_calls: int = 1,
    max_attempts: int = 0,
    rate_limit: RateLimitPolicy | None = None,
) -> RuntimeCoordinator:
    coordinator = RuntimeCoordinator(
        ExecutionPolicy(
            retry=RetryPolicy(max_attempts=max_attempts, base_delay_seconds=0.01),
            rate_limit=rate_limit or RateLimitPolicy(),
        )
    )
    coordinator.get_circuit_breaker(
        "openai",
        CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=recovery_timeout_seconds,
            half_open_max_calls=half_open_max_calls,
        ),
    )
    return coordinator


async def _trip_open(coordinator: RuntimeCoordinator) -> None:
    async def fail(request: ExecutionRequest) -> str:
        raise RateLimitExceeded(message="slow down")

    result = await coordinator.execute(_request(), fail)
    assert result.success is False
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.OPEN
    await asyncio.sleep(0.08)


class TestHalfOpenAdmissionUnit:
    """Breaker-level admission, release, and generation semantics."""

    def test_max_one_admits_exactly_one(self) -> None:
        breaker = RuntimeCircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, half_open_max_calls=1)
        )
        breaker.record_failure()
        breaker._transition_to(RuntimeCircuitState.HALF_OPEN)
        first = breaker.acquire()
        second = breaker.acquire()
        assert first.admitted is True
        assert first.reserved is True
        assert second.admitted is False
        assert second.exhausted is True
        assert breaker.half_open_in_flight == 1

    def test_release_allows_readmission(self) -> None:
        breaker = RuntimeCircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, half_open_max_calls=1)
        )
        breaker.record_failure()
        breaker._transition_to(RuntimeCircuitState.HALF_OPEN)
        ticket = breaker.acquire()
        breaker.release_probe(ticket.generation)
        assert breaker.half_open_in_flight == 0
        assert breaker.acquire().admitted is True

    def test_closed_and_open_bypass_probe_accounting(self) -> None:
        breaker = RuntimeCircuitBreaker(CircuitBreakerConfig(failure_threshold=5))
        assert breaker.acquire().admitted is True
        assert breaker.acquire().reserved is False
        assert breaker.half_open_in_flight == 0

    def test_stale_completion_is_ignored(self) -> None:
        breaker = RuntimeCircuitBreaker(CircuitBreakerConfig(failure_threshold=1))
        breaker.record_failure()
        breaker._transition_to(RuntimeCircuitState.HALF_OPEN)
        ticket = breaker.acquire()
        breaker.record_failure()  # same-episode probe fails -> OPEN, new generation
        assert breaker.state == RuntimeCircuitState.OPEN
        before = breaker.snapshot().success_count
        breaker.record_success(ticket.generation)  # stale: ignored entirely
        assert breaker.state == RuntimeCircuitState.OPEN
        assert breaker.snapshot().success_count == before
        assert breaker.half_open_in_flight == 0


@pytest.mark.asyncio
async def test_concurrent_probes_capped_at_one_with_zero_extra_calls() -> None:
    coordinator = _coordinator()
    await _trip_open(coordinator)

    gate = asyncio.Event()
    started = 0

    async def probe(request: ExecutionRequest) -> str:
        nonlocal started
        started += 1
        await gate.wait()
        return "ok"

    tasks = [asyncio.create_task(coordinator.execute(_request(), probe)) for _ in range(5)]
    await asyncio.sleep(0.1)
    assert started == 1
    gate.set()
    results = await asyncio.gather(*tasks)

    assert sum(1 for r in results if r.success) == 1
    denied = [r for r in results if not r.success]
    assert len(denied) == 4
    assert started == 1
    for result in denied:
        assert result.telemetry.error_code == "CIRCUIT_BREAKER_OPEN"
        assert "half-open probe capacity exhausted" in result.error
    assert coordinator.get_circuit_breaker("openai").half_open_in_flight == 0


@pytest.mark.asyncio
async def test_sequential_probes_close_after_threshold() -> None:
    coordinator = RuntimeCoordinator(
        ExecutionPolicy(retry=RetryPolicy(max_attempts=0, base_delay_seconds=0.01))
    )
    coordinator.get_circuit_breaker(
        "openai",
        CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.05,
            half_open_max_calls=1,
            success_threshold=2,
        ),
    )
    await _trip_open(coordinator)

    async def ok(request: ExecutionRequest) -> str:
        return "ok"

    assert (await coordinator.execute(_request(), ok)).success is True
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.HALF_OPEN
    assert (await coordinator.execute(_request(), ok)).success is True
    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.CLOSED


@pytest.mark.asyncio
async def test_retryable_probe_failure_releases_and_reopens() -> None:
    coordinator = _coordinator()
    await _trip_open(coordinator)

    async def fail(request: ExecutionRequest) -> str:
        raise RateLimitExceeded(message="slow down")

    result = await coordinator.execute(_request(), fail)
    assert result.success is False
    breaker = coordinator.get_circuit_breaker("openai")
    assert breaker.state == RuntimeCircuitState.OPEN
    assert breaker.half_open_in_flight == 0


@pytest.mark.asyncio
async def test_fatal_probe_failure_releases_without_recording() -> None:
    coordinator = _coordinator()
    await _trip_open(coordinator)
    breaker = coordinator.get_circuit_breaker("openai")
    failures_before = breaker.snapshot().failure_count

    async def fatal(request: ExecutionRequest) -> str:
        raise AuthenticationRequired(message="bad key")

    async def ok(request: ExecutionRequest) -> str:
        return "ok"

    result = await coordinator.execute(_request(), fatal)
    assert result.success is False
    assert breaker.state == RuntimeCircuitState.HALF_OPEN
    assert breaker.half_open_in_flight == 0
    assert breaker.snapshot().failure_count == failures_before
    # A subsequent probe is still admitted and can close the breaker.
    assert (await coordinator.execute(_request(), ok)).success is True
    assert breaker.state == RuntimeCircuitState.CLOSED


@pytest.mark.asyncio
async def test_timeout_probe_releases_reservation() -> None:
    coordinator = _coordinator()
    await _trip_open(coordinator)

    async def slow(request: ExecutionRequest) -> str:
        await asyncio.sleep(30)
        return "too late"

    started = time.monotonic()
    result = await coordinator.execute(_request(timeout_seconds=0.15), slow)
    elapsed = time.monotonic() - started
    assert result.success is False
    assert "timed out" in result.error.lower()
    assert elapsed < 10
    breaker = coordinator.get_circuit_breaker("openai")
    assert breaker.state == RuntimeCircuitState.OPEN
    assert breaker.half_open_in_flight == 0


@pytest.mark.asyncio
async def test_cancelled_probe_releases_without_recording() -> None:
    coordinator = _coordinator()
    await _trip_open(coordinator)
    breaker = coordinator.get_circuit_breaker("openai")
    failures_before = breaker.snapshot().failure_count

    async def slow(request: ExecutionRequest) -> str:
        await asyncio.sleep(30)
        return "too late"

    task = asyncio.create_task(coordinator.execute(_request(), slow))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert breaker.half_open_in_flight == 0
    assert breaker.snapshot().failure_count == failures_before


@pytest.mark.asyncio
async def test_breaker_denial_consumes_no_rate_quota() -> None:
    # Long recovery keeps the breaker OPEN for the assertion (a short
    # timeout would legitimately recover to HALF_OPEN mid-test).
    coordinator = _coordinator(
        recovery_timeout_seconds=300,
        rate_limit=RateLimitPolicy(requests_per_minute=10),
    )
    limiter = coordinator.get_rate_limiter("openai")
    for _ in range(3):
        limiter.record_request("openai")
    await _trip_open(coordinator)

    async def ok(request: ExecutionRequest) -> str:
        return "ok"

    assert coordinator.get_circuit_breaker("openai").state == RuntimeCircuitState.OPEN
    denied = await coordinator.execute(_request(), ok)
    assert denied.success is False
    assert denied.telemetry.error_code == "CIRCUIT_BREAKER_OPEN"
    # 3 prefilled + 1 trip call; the breaker-denied call added nothing.
    assert len(limiter._request_timestamps["openai"]) == 4


@pytest.mark.asyncio
async def test_rate_denial_after_admission_releases_probe() -> None:
    coordinator = _coordinator(rate_limit=RateLimitPolicy(requests_per_minute=1))
    await _trip_open(coordinator)
    # Exhaust the quota only after the trip (prefilling first would
    # deny the trip call itself and never open the breaker).
    coordinator.get_rate_limiter("openai").record_request("openai")
    await asyncio.sleep(0.08)
    breaker = coordinator.get_circuit_breaker("openai")
    assert breaker.state == RuntimeCircuitState.HALF_OPEN

    async def ok(request: ExecutionRequest) -> str:
        return "ok"

    denied = await coordinator.execute(_request(), ok)
    assert denied.success is False
    assert denied.telemetry.error_code == "RATE_LIMIT_EXCEEDED"
    assert breaker.state == RuntimeCircuitState.HALF_OPEN
    assert breaker.half_open_in_flight == 0


@pytest.mark.asyncio
async def test_failed_probe_denies_subsequent_retry_attempt() -> None:
    coordinator = _coordinator(max_attempts=2)
    await _trip_open(coordinator)
    calls = 0

    async def fail(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise RateLimitExceeded(message="slow down")

    result = await coordinator.execute(_request(), fail)
    assert result.success is False
    # First attempt consumed the single probe and reopened; the retry
    # was denied before invocation: no unbounded extra probes.
    assert calls == 1
    assert "circuit breaker" in result.error.lower()


@pytest.mark.asyncio
async def test_mixed_concurrent_probes_stale_loser_ignored() -> None:
    coordinator = RuntimeCoordinator(
        ExecutionPolicy(retry=RetryPolicy(max_attempts=0, base_delay_seconds=0.01))
    )
    coordinator.get_circuit_breaker(
        "openai",
        CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout_seconds=0.05,
            half_open_max_calls=2,
        ),
    )
    await _trip_open(coordinator)
    breaker = coordinator.get_circuit_breaker("openai")

    gate_a = asyncio.Event()
    gate_b = asyncio.Event()

    async def fail_a(request: ExecutionRequest) -> str:
        await gate_a.wait()
        raise RateLimitExceeded(message="slow down")

    async def ok_b(request: ExecutionRequest) -> str:
        await gate_b.wait()
        return "ok"

    task_a = asyncio.create_task(coordinator.execute(_request(), fail_a))
    task_b = asyncio.create_task(coordinator.execute(_request(), ok_b))
    await asyncio.sleep(0.1)
    assert breaker.half_open_in_flight == 2
    gate_a.set()
    # Await the task (event-driven, no sleep): asserting after a sleep
    # would let the short recovery timeout legitimately rotate the
    # reopened breaker back to HALF_OPEN before we observe it.
    await task_a
    assert breaker.state == RuntimeCircuitState.OPEN
    assert breaker.snapshot().failure_count == 2
    gate_b.set()
    result_b = await task_b
    assert result_b.success is True
    # B's success arrived in a superseded episode: must not close the breaker.
    assert breaker.state == RuntimeCircuitState.OPEN
    assert breaker.half_open_in_flight == 0


@pytest.mark.asyncio
async def test_closed_and_open_behavior_unchanged() -> None:
    coordinator = _coordinator()
    breaker = coordinator.get_circuit_breaker("openai")
    calls = 0

    async def ok(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert (await coordinator.execute(_request(), ok)).success is True
    assert breaker.half_open_in_flight == 0
    assert calls == 1


@pytest.mark.asyncio
async def test_provider_isolation_unchanged() -> None:
    coordinator = _coordinator()
    await _trip_open(coordinator)

    async def ok(request: ExecutionRequest) -> str:
        return "ok"

    result = await coordinator.execute(_request(provider_name="anthropic"), ok)
    assert result.success is True
