"""Tests for coordinator."""

import pytest

from app.providers.runtime.execution.runtime_coordinator import (
    ExecutionRequest,
    RuntimeCoordinator,
    RuntimeExecutionResult,
)
from app.providers.runtime.policies.runtime_policies import ExecutionPolicy, RetryPolicy


class TestRuntimeCoordinator:
    """Tests for RuntimeCoordinator."""

    def test_initial_state(self) -> None:
        coordinator = RuntimeCoordinator()
        assert coordinator.execution_count == 0
        assert coordinator.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_successful_execution(self) -> None:
        coordinator = RuntimeCoordinator()
        request = ExecutionRequest(
            provider_name="openai",
            model_id="gpt-4",
            request_id="req-1",
        )

        async def handler(r: ExecutionRequest) -> str:
            return "success"

        result = await coordinator.execute(request, handler)
        assert result.success is True
        assert result.response == "success"
        assert result.provider_used == "openai"
        assert coordinator.execution_count == 1

    @pytest.mark.asyncio
    async def test_failed_execution_with_retry(self) -> None:
        policy = ExecutionPolicy(
            retry=RetryPolicy(max_attempts=2, base_delay_seconds=0.01),
        )
        coordinator = RuntimeCoordinator(policy)
        request = ExecutionRequest(
            provider_name="openai",
            model_id="gpt-4",
            request_id="req-2",
        )

        call_count = 0

        async def handler(r: ExecutionRequest) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "recovered"

        result = await coordinator.execute(request, handler)
        assert result.success is True
        assert result.response == "recovered"

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self) -> None:
        from app.providers.runtime.circuit_breaker.runtime_circuit_breaker import CircuitBreakerConfig

        policy = ExecutionPolicy(
            retry=RetryPolicy(max_attempts=0),
        )
        coordinator = RuntimeCoordinator(policy)
        cb = coordinator.get_circuit_breaker(
            "openai", CircuitBreakerConfig(failure_threshold=2)
        )

        request = ExecutionRequest(provider_name="openai", model_id="gpt-4", request_id="req-3")

        async def handler(r: ExecutionRequest) -> str:
            raise ValueError("fail")

        await coordinator.execute(request, handler)
        await coordinator.execute(request, handler)

        result = await coordinator.execute(request, handler)
        assert result.success is False
        assert "circuit breaker" in result.error.lower() or "CircuitBreakerOpenError" in result.error

    def test_circuit_breaker_singleton(self) -> None:
        coordinator = RuntimeCoordinator()
        cb1 = coordinator.get_circuit_breaker("openai")
        cb2 = coordinator.get_circuit_breaker("openai")
        assert cb1 is cb2

    def test_fallback_configuration(self) -> None:
        from app.providers.runtime.fallback.fallback_chain import FallbackEntry

        coordinator = RuntimeCoordinator()
        coordinator.configure_fallback(
            "default",
            [
                FallbackEntry(provider_name="openai", model_id="gpt-4"),
                FallbackEntry(provider_name="anthropic", model_id="claude"),
            ],
        )
        assert "default" in coordinator._state.fallback_chains
