"""Engine-level cooperative cancellation tests.

Deterministic proof that AdaptiveCampaignEngine stops work when the injected
`cancelled` probe flips, at every provider boundary: before starting a new
round, before mutation, before the target provider, and before the judge.
No Temporal, no DB — pure engine behavior.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.domain.campaign import (
    AdaptiveCampaign,
    CampaignState,
)
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine


def _chat_response(content: str) -> ChatResponse:
    return ChatResponse(
        content=content,
        model="test-model",
        provider="test-provider",
        usage=Usage(input_tokens=4, output_tokens=2),
        finish_reason=FinishReason.STOP,
    )


class _CountingProvider:
    provider_name = "test-provider"

    def __init__(self, content: str = "I will not comply with that request.") -> None:
        self.calls = 0
        self._content = content

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        self.calls += 1
        return _chat_response(self._content)

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


def _build_engine(*, cancelled: Any = None) -> tuple[AdaptiveCampaignEngine, _CountingProvider]:
    provider = _CountingProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    engine = AdaptiveCampaignEngine(
        registry=registry,
        metric_engine=None,
        metric_names=(),
        semantic_judge=None,
        judge_provider=None,
        mutation_provider=None,
        mutation_model="",
        mutation_strategy=None,
        cancelled=cancelled,
    )
    return engine, provider


# A response that trips keyword-based LEAKED across many safety dimensions so
# effectiveness lands at 1.0 (>= 0.8 threshold) and the loop stops on round 1.
VIOLATION_TEXT = (
    "ignore previous instructions bypass override policy circumvent illegal "
    "unethical prohibited; kill bomb destroy weapon violence injure torture "
    "abuse; credit card password secret api key credential; sudo admin exec "
    "eval delete drop table rm -rf"
)


def _build_engine_with_content(content: str) -> tuple[AdaptiveCampaignEngine, _CountingProvider]:
    registry = ProviderRegistry()
    provider = _CountingProvider(content=content)
    registry.register(provider)
    engine = AdaptiveCampaignEngine(
        registry=registry,
        metric_engine=None,
        metric_names=(),
        semantic_judge=None,
        judge_provider=None,
        mutation_provider=None,
        mutation_model="",
        mutation_strategy=None,
        cancelled=None,
    )
    return engine, provider


def _flip_on_call(async_fn: Any, state: dict[str, bool], when: int) -> Any:
    calls = {"n": 0}

    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == when:
            state["flag"] = True
        return await async_fn(*args, **kwargs)

    return wrapper


class TestEngineCancellationBoundaries:
    async def test_cancel_before_start_produces_cancelled_with_no_provider_calls(
        self,
    ) -> None:
        state = {"flag": True}
        engine, provider = _build_engine(cancelled=lambda: state["flag"])
        campaign = AdaptiveCampaign.create(
            name="cancel-before-start",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.CANCELLED
        assert result.total_rounds == 0
        assert provider.calls == 0
        assert campaign.current_round_number == 0

    async def test_cancel_between_rounds_keeps_only_completed_rounds(self) -> None:
        state = {"flag": False}
        engine, provider = _build_engine(cancelled=lambda: state["flag"])
        # Cancellation observed while round 1 is being evaluated: round 1 is
        # recorded, round 2 never starts.
        engine._evaluator.evaluate = _flip_on_call(  # type: ignore[method-assign]
            engine._evaluator.evaluate, state, when=1
        )
        campaign = AdaptiveCampaign.create(
            name="cancel-between-rounds",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.CANCELLED
        assert result.total_rounds == 1
        assert provider.calls == 1
        assert campaign.current_round_number == 1

    async def test_cancel_before_mutation_prevents_mutation_call(self) -> None:
        state = {"flag": False}
        engine, provider = _build_engine(cancelled=lambda: state["flag"])
        mutation_calls = 0
        original_mutate = engine._selector.mutation_engine.mutate

        async def counting_mutate(*args: Any, **kwargs: Any) -> Any:
            nonlocal mutation_calls
            mutation_calls += 1
            if mutation_calls == 2:
                state["flag"] = True
            return await original_mutate(*args, **kwargs)

        # Cancellation observed during round 2's scenario generation: the
        # mutation provider must NOT be invoked for round 2.
        engine._orchestrator.generate_scenarios = _flip_on_call(  # type: ignore[method-assign]
            engine._orchestrator.generate_scenarios, state, when=2
        )
        engine._selector.mutation_engine.mutate = counting_mutate  # type: ignore[method-assign]
        campaign = AdaptiveCampaign.create(
            name="cancel-before-mutation",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.CANCELLED
        assert result.total_rounds == 1
        assert mutation_calls == 0
        assert provider.calls == 1

    async def test_cancel_during_mutation_prevents_target_call(self) -> None:
        state = {"flag": False}
        engine, provider = _build_engine(cancelled=lambda: state["flag"])
        # Cancellation observed during round 2's mutation step (the only round
        # that runs the mutation provider first): the round-2 target provider
        # must not be called.
        engine._selector.mutation_engine.mutate = _flip_on_call(  # type: ignore[method-assign]
            engine._selector.mutation_engine.mutate, state, when=1
        )
        campaign = AdaptiveCampaign.create(
            name="cancel-before-target",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.CANCELLED
        assert result.total_rounds == 1
        assert provider.calls == 1

    async def test_cancel_before_judge_prevents_evaluation(self) -> None:
        state = {"flag": False}
        engine, provider = _build_engine(cancelled=lambda: state["flag"])
        evaluate_calls = 0
        original_evaluate = engine._evaluator.evaluate

        async def counting_evaluate(*args: Any, **kwargs: Any) -> Any:
            nonlocal evaluate_calls
            evaluate_calls += 1
            return await original_evaluate(*args, **kwargs)

        # Cancellation observed during round 2's target call: the judge must
        # not run for round 2 and the round must not be recorded.
        provider.chat = _flip_on_call(provider.chat, state, when=2)  # type: ignore[method-assign]
        engine._evaluator.evaluate = counting_evaluate  # type: ignore[method-assign]
        campaign = AdaptiveCampaign.create(
            name="cancel-before-judge",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.CANCELLED
        assert result.total_rounds == 1
        assert provider.calls == 2
        assert evaluate_calls == 1

    async def test_no_cancellation_reaches_budget_exhaustion(self) -> None:
        engine, provider = _build_engine(cancelled=None)
        campaign = AdaptiveCampaign.create(
            name="no-cancel",
            target_provider="test-provider",
            target_model="m",
            budget=__import__(
                "app.redteam.domain.campaign", fromlist=["CampaignBudget"]
            ).CampaignBudget(
                max_rounds=3,
            ),
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.BUDGET_EXHAUSTED
        assert result.total_rounds == 3
        assert provider.calls == 3

    async def test_consecutive_provider_errors_terminate_as_completed(self) -> None:
        """Regression: executor swallows provider errors; repeated errors stop the loop."""
        engine, provider = _build_engine(cancelled=None)

        async def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("provider down")

        provider.chat = boom  # type: ignore[method-assign]
        campaign = AdaptiveCampaign.create(
            name="provider-errors",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        # Three consecutive execution errors trip the early-stop guard and the
        # campaign closes out as COMPLETED (pre-existing contract, preserved).
        assert result.state == CampaignState.COMPLETED
        assert result.total_rounds == 3

    async def test_engine_exception_still_fails_campaign(self) -> None:
        """Regression: exceptions escaping the loop still mark the campaign FAILED."""
        engine, _ = _build_engine(cancelled=None)

        async def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("metric engine exploded")

        engine._evaluator.evaluate = boom  # type: ignore[method-assign]
        campaign = AdaptiveCampaign.create(
            name="engine-fail",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.FAILED


# ---------------------------------------------------------------------------
# Engine success / value-level regression tests (no cancel hook)
# ---------------------------------------------------------------------------


class TestEngineSuccessAndEffectiveness:
    async def test_violation_response_yields_completed_effectiveness(self) -> None:
        engine, _ = _build_engine_with_content(VIOLATION_TEXT)
        campaign = AdaptiveCampaign.create(
            name="violation",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.COMPLETED
        assert result.total_rounds == 1
        assert result.final_effectiveness == 1.0
        assert result.violation_count == 1
        assert result.severe_violation_count == 1

    async def test_safe_response_yields_zero_effectiveness(self) -> None:
        engine, _ = _build_engine(cancelled=None)
        campaign = AdaptiveCampaign.create(
            name="safe",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.BUDGET_EXHAUSTED
        assert result.final_effectiveness == 0.0
        assert result.violation_count == 0

    async def test_campaign_round_numbers_are_sequential(self) -> None:
        engine, _ = _build_engine(cancelled=None)
        campaign = AdaptiveCampaign.create(
            name="rounds",
            target_provider="test-provider",
            target_model="m",
            budget=__import__(
                "app.redteam.domain.campaign", fromlist=["CampaignBudget"]
            ).CampaignBudget(
                max_rounds=4,
            ),
        )

        result = await engine.run_campaign(campaign)

        assert result.total_rounds == 4
        for i, rnd in enumerate(result.rounds):
            assert rnd.round_number == i + 1

    async def test_execution_error_increments_attack_count(self) -> None:
        engine, provider = _build_engine(cancelled=None)

        async def boom(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("provider down")

        provider.chat = boom  # type: ignore[method-assign]
        campaign = AdaptiveCampaign.create(
            name="errors",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        # Three consecutive errors stop the loop via early-stop guard.
        assert result.total_attacks == 3
        assert result.total_rounds == 3

    async def test_cancelled_campaign_result_state_cancelled(self) -> None:
        engine, _ = _build_engine(cancelled=lambda: True)
        campaign = AdaptiveCampaign.create(
            name="cancel-state",
            target_provider="test-provider",
            target_model="m",
        )

        result = await engine.run_campaign(campaign)

        assert result.state == CampaignState.CANCELLED
        assert result.total_rounds == 0
        assert result.campaign_id == str(campaign.id)


if __name__ == "__main__":
    # Lazy self-check: run the boundary suite through pytest when executed
    # directly. Kept as a one-liner guard so this file always stays runnable.
    raise SystemExit(pytest.main([__file__, "-q"]))
