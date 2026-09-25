"""Regression tests: provider runtime retry taxonomy and timeout enforcement.

Proven defects in RuntimeCoordinator.execute:
* the retry evaluator's code allowlist is empty by default AND the
  coordinator never reads ``exc.retryable``, so fatal errors
  (bad credentials, unknown model, context overflow) are re-POSTed as
  paid calls up to max_attempts;
* the timeout check is fed per-attempt start (elapsed ~0, never fires)
  and the handler await is never bounded, so ``timeout_seconds`` is
  decorative and only the SDK 120s guard exists.

Fix contract locked here:
* ``retryable is False`` short-circuits before any sleep/retry;
  unclassified errors keep current retry behavior;
* per-request ``timeout_seconds`` bounds handler execution (asyncio
  timeout -> ExecutionTimeoutError -> normal retry taxonomy);
* the evaluator clock uses execution start.

Fake handlers only — no provider credentials involved.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.providers.exceptions.auth import AuthenticationRequired
from app.providers.exceptions.limits import ContextWindowExceeded
from app.providers.exceptions.model import InvalidModel
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.runtime.execution.runtime_coordinator import (
    ExecutionRequest,
    RuntimeCoordinator,
)
from app.providers.runtime.policies.runtime_policies import (
    ExecutionPolicy,
    RetryPolicy,
    TimeoutPolicy,
)


def _request(**overrides) -> ExecutionRequest:
    args = {
        "provider_name": "openai",
        "model_id": "gpt-4o",
        "request_id": "req-test",
    }
    args.update(overrides)
    return ExecutionRequest(**args)


def _policy(**overrides) -> ExecutionPolicy:
    retry = RetryPolicy(max_attempts=3, base_delay_seconds=0.01)
    return ExecutionPolicy(retry=retry, **overrides)


@pytest.mark.asyncio
async def test_fatal_auth_error_is_not_retried() -> None:
    coordinator = RuntimeCoordinator(_policy())
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise AuthenticationRequired(message="bad key")

    result = await coordinator.execute(_request(), handler)
    assert result.success is False
    assert calls == 1


@pytest.mark.asyncio
async def test_fatal_model_and_context_errors_are_not_retried() -> None:
    coordinator = RuntimeCoordinator(_policy())
    calls: list[str] = []

    async def bad_model(request: ExecutionRequest) -> str:
        calls.append("model")
        raise InvalidModel(message="no such model", model_id="nope")

    async def too_long(request: ExecutionRequest) -> str:
        calls.append("context")
        raise ContextWindowExceeded(message="too long")

    assert (await coordinator.execute(_request(), bad_model)).success is False
    assert (await coordinator.execute(_request(), too_long)).success is False
    assert calls == ["model", "context"]


@pytest.mark.asyncio
async def test_transient_errors_still_retry_then_recover() -> None:
    coordinator = RuntimeCoordinator(_policy())
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


@pytest.mark.asyncio
async def test_unclassified_errors_keep_legacy_retry_behavior() -> None:
    policy = ExecutionPolicy(retry=RetryPolicy(max_attempts=2, base_delay_seconds=0.01))
    coordinator = RuntimeCoordinator(policy)
    calls = 0

    async def handler(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("transient-ish")
        return "recovered"

    result = await coordinator.execute(_request(), handler)
    assert result.success is True
    assert calls == 3


@pytest.mark.asyncio
async def test_handler_bounded_by_request_timeout() -> None:
    policy = ExecutionPolicy(retry=RetryPolicy(max_attempts=0))
    coordinator = RuntimeCoordinator(policy)

    async def slow(request: ExecutionRequest) -> str:
        await asyncio.sleep(30)
        return "too late"

    started = time.monotonic()
    result = await coordinator.execute(_request(timeout_seconds=0.2), slow)
    elapsed = time.monotonic() - started
    assert result.success is False
    assert elapsed < 10


@pytest.mark.asyncio
async def test_evaluator_clock_uses_execution_start() -> None:
    from app.providers.runtime.circuit_breaker.runtime_circuit_breaker import (
        CircuitBreakerConfig,
    )

    policy = ExecutionPolicy(
        retry=RetryPolicy(max_attempts=100, base_delay_seconds=0.01),
        timeout=TimeoutPolicy(request_timeout_seconds=0.05),
    )
    coordinator = RuntimeCoordinator(policy)
    coordinator.get_circuit_breaker(
        "openai", CircuitBreakerConfig(failure_threshold=10000)
    )
    calls = 0

    async def instant_fail(request: ExecutionRequest) -> str:
        nonlocal calls
        calls += 1
        raise RateLimitExceeded(message="slow down")

    started = time.monotonic()
    result = await coordinator.execute(_request(), instant_fail)
    elapsed = time.monotonic() - started
    assert result.success is False
    assert "timeout" in result.error.lower()
    assert calls < 50
    assert elapsed < 10
