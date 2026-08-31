"""Production-path tests proving LLM mutation is wired into the real campaign.

These exercise the actual ``AdaptiveCampaignEngine`` (the same class the
red-team Temporal activity instantiates) with a deterministic fake LLM
provider, proving:

1. A campaign configured for LLM mutation invokes the LLM mutator.
2. The mutator receives the original attack/input.
3. The configured provider/model is used for the mutation call.
4. The generated mutation is passed into the target execution path.
5. The target receives the mutated attack, not the original attack.
6. Provenance (source=llm_variation) and the original prompt are preserved.
7. Explicit LLM mutation without a provider fails clearly.
8. Template/non-LLM mutation behavior is unchanged.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.kernel.exceptions.errors import ValidationError
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.domain.campaign import AdaptiveCampaign, CampaignBudget
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine
from app.redteam.engine.mutation import MutationEngine, MutationStrategy
from app.redteam.engine.mutation_selector import MutationStrategySelector


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _chat_response(content: str) -> ChatResponse:
    return ChatResponse(
        content=content,
        model="test-model",
        provider="test-provider",
        usage=Usage(input_tokens=10, output_tokens=5),
        finish_reason=FinishReason.STOP,
    )


def _target_registry() -> ProviderRegistry:
    """A registry with one target provider returning a safe response."""

    class _TargetProvider:
        provider_name = "test-provider"

        async def chat(self, messages, *, model, options=None) -> ChatResponse:
            return _chat_response("I cannot help with that")

        async def health(self) -> bool:
            return True

        def capabilities(self):
            return object()

    registry = ProviderRegistry()
    registry.register(_TargetProvider())
    return registry


_VARIATIONS = "malicious-variation-one\nmalicious-variation-two"


def _llm_mutation_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.chat.return_value = _chat_response(_VARIATIONS)
    return provider


class TestCampaignLLMMutationProductionPath:
    def test_campaign_invokes_llm_mutator_and_uses_mutation_for_target(self) -> None:
        registry = _target_registry()
        llm = _llm_mutation_provider()

        engine = AdaptiveCampaignEngine(
            registry,
            mutation_provider=llm,
            mutation_model="mutator-model",
            mutation_strategy=MutationStrategy.PROMPT_VARIATION,
        )

        campaign = AdaptiveCampaign.create(
            name="LLM Mutation Path",
            target_provider="test-provider",
            target_model="test-model",
            budget=CampaignBudget(max_rounds=3, max_attacks=3),
        )

        result = _run(engine.run_campaign(campaign))

        assert result.total_rounds == 3

        # Seed round (0) is not mutated.
        seed_round = result.rounds[0]
        assert seed_round.lineage.is_seed

        # The LLM mutator was invoked with the configured model.
        assert llm.chat.called
        _, kwargs = llm.chat.call_args
        assert kwargs["model"] == "mutator-model"

        # A mutated round (> 0) records the LLM-generated mutation as the
        # exact prompt sent to the target.
        mutated_round = result.rounds[1]
        assert mutated_round.mutation_strategy == MutationStrategy.PROMPT_VARIATION.value
        assert mutated_round.execution is not None
        assert mutated_round.execution.attack_prompt == "malicious-variation-one"

        # The target received the mutated prompt, not that round's original.
        original_prompt = result.rounds[1].attack_scenario.metadata.get("original_prompt")
        assert original_prompt
        assert mutated_round.execution.attack_prompt != original_prompt

        # Provenance is flagged on the mutated scenario.
        assert mutated_round.attack_scenario.metadata.get("source") == "llm_variation"

    def test_fake_llm_receives_original_attack_prompt(self) -> None:
        registry = _target_registry()
        llm = _llm_mutation_provider()

        engine = AdaptiveCampaignEngine(
            registry,
            mutation_provider=llm,
            mutation_model="m",
            mutation_strategy=MutationStrategy.PROMPT_VARIATION,
        )
        campaign = AdaptiveCampaign.create(
            name="LLM Input",
            target_provider="test-provider",
            target_model="test-model",
            budget=CampaignBudget(max_rounds=2, max_attacks=2),
        )

        result = _run(engine.run_campaign(campaign))
        mutated_round = result.rounds[1]
        original_prompt = mutated_round.attack_scenario.metadata.get("original_prompt")
        assert original_prompt

        assert llm.chat.called
        messages, _ = llm.chat.call_args
        # The mutator's user message must embed that round's original attack prompt.
        user_contents = " ".join(m.content for m in messages[0] if getattr(m, "role", "") == "user")
        assert original_prompt in user_contents


class TestExplicitLLMMutationFailureSemantics:
    def test_explicit_llm_variation_without_provider_fails_clearly(self) -> None:
        with pytest.raises(ValidationError):
            AdaptiveCampaignEngine(
                _target_registry(),
                mutation_strategy=MutationStrategy.PROMPT_VARIATION,
            )

    def test_explicit_llm_variation_without_model_fails_clearly(self) -> None:
        with pytest.raises(ValidationError):
            AdaptiveCampaignEngine(
                _target_registry(),
                mutation_provider=_llm_mutation_provider(),
                mutation_strategy=MutationStrategy.PROMPT_VARIATION,
            )


class TestTemplateMutationUnchanged:
    def test_template_mutation_without_provider_uses_suffix_fallback(self) -> None:
        llm = AsyncMock()
        engine = MutationEngine()  # no provider

        result = _run(engine.mutate("original prompt", MutationStrategy.PROMPT_VARIATION))

        # Without a provider, LLM variation falls back to a static suffix.
        assert result[0].strategy == MutationStrategy.ADVERSARIAL_SUFFIX
        assert llm.chat.call_count == 0
        assert result[0].metadata.get("source") != "llm_variation"

    def test_template_mutation_without_provider_keeps_template_behavior(self) -> None:
        registry = _target_registry()
        engine = AdaptiveCampaignEngine(
            registry,
            mutation_strategy=MutationStrategy.ENCODING_BASE64,
        )
        campaign = AdaptiveCampaign.create(
            name="Template Path",
            target_provider="test-provider",
            target_model="test-model",
            budget=CampaignBudget(max_rounds=2, max_attacks=2),
        )

        result = _run(engine.run_campaign(campaign))

        mutated_round = result.rounds[1]
        assert mutated_round.mutation_strategy == MutationStrategy.ENCODING_BASE64.value
        assert mutated_round.execution is not None
        assert "base64" in mutated_round.execution.attack_prompt.lower()


class TestSelectorLLMWiring:
    async def test_selector_passes_provider_and_model_to_engine(self) -> None:
        llm = _llm_mutation_provider()
        selector = MutationStrategySelector(
            llm_provider=llm,
            llm_model="selector-model",
        )

        result = await selector.apply_mutation(
            "base prompt",
            MutationStrategy.PROMPT_VARIATION,
        )

        assert result.mutated_prompt == "malicious-variation-one"
        assert result.metadata.get("source") == "llm_variation"
        assert result.strategy == MutationStrategy.PROMPT_VARIATION
        assert llm.chat.called
        _, kwargs = llm.chat.call_args
        assert kwargs["model"] == "selector-model"
