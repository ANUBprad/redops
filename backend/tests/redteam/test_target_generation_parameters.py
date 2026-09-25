"""P6-B1: target generation parameter propagation tests.

Deterministic provider-boundary proof that configured temperature/max_tokens
survive the full path:

    AttackConfiguration / AdaptiveCampaign
        → AdaptiveCampaignEngine
        → TargetExecutor.execute(...)
        → ChatOptions
        → provider.chat(...)

No Temporal, no DB, no live provider calls — pure engine tests with a fake
provider that records the exact ChatOptions it received.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.providers.models.enums import FinishReason
from app.providers.models.options import ChatOptions
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.domain.campaign import AdaptiveCampaign, CampaignBudget
from app.redteam.domain.enums import AttackCategory
from app.redteam.engine.campaign_engine import AdaptiveCampaignEngine


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _chat_response(content: str = "I will not comply with that request.") -> ChatResponse:
    return ChatResponse(
        content=content,
        model="probe-model",
        provider="probe-provider",
        usage=Usage(input_tokens=4, output_tokens=2),
        finish_reason=FinishReason.STOP,
    )


class _RecordingProvider:
    provider_name = "probe-provider"

    def __init__(self, content: str = "I will not comply with that request.") -> None:
        self.chats: list[ChatOptions | None] = []
        self._content = content

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        self.chats.append(options)
        return _chat_response(self._content)

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


def _build_engine(provider: _RecordingProvider) -> AdaptiveCampaignEngine:
    registry = ProviderRegistry()
    registry.register(provider)
    return AdaptiveCampaignEngine(
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


def _make_campaign(**target_params: Any) -> AdaptiveCampaign:
    return AdaptiveCampaign.create(
        name="P6-B1 campaign",
        target_provider="probe-provider",
        target_model="probe-model",
        budget=CampaignBudget(max_rounds=2, max_attacks=2),
        **target_params,
    )


class TestTargetGenerationParameters:
    def test_configured_temperature_reaches_provider_chat(self) -> None:
        provider = _RecordingProvider()
        engine = _build_engine(provider)
        campaign = _make_campaign(target_temperature=0.7)

        _run(engine.run_campaign(campaign))

        assert len(provider.chats) == 2  # round boundaries unchanged
        assert all(isinstance(o, ChatOptions) for o in provider.chats)
        assert all(o.temperature == 0.7 for o in provider.chats)

    def test_configured_max_tokens_reaches_provider_chat(self) -> None:
        provider = _RecordingProvider()
        engine = _build_engine(provider)
        campaign = _make_campaign(target_max_tokens=4096)

        _run(engine.run_campaign(campaign))

        assert len(provider.chats) == 2
        assert all(o.max_tokens == 4096 for o in provider.chats)

    def test_configured_temperature_and_max_tokens_reach_provider_together(self) -> None:
        provider = _RecordingProvider()
        engine = _build_engine(provider)
        campaign = _make_campaign(target_temperature=0.7, target_max_tokens=4096)

        _run(engine.run_campaign(campaign))

        assert len(provider.chats) == 2
        assert all(o.temperature == 0.7 and o.max_tokens == 4096 for o in provider.chats)

    def test_omitted_values_preserve_domain_defaults_at_provider_boundary(self) -> None:
        provider = _RecordingProvider()
        engine = _build_engine(provider)
        campaign = _make_campaign()

        _run(engine.run_campaign(campaign))

        assert len(provider.chats) == 2
        # Domain defaults (0.0/2048) match the executor defaults exactly,
        # so omitting values behaves identically to the pre-fix path.
        assert all(o.temperature == 0.0 and o.max_tokens == 2048 for o in provider.chats)

    def test_single_attack_respects_configured_parameters(self) -> None:
        provider = _RecordingProvider()
        engine = _build_engine(provider)
        campaign = _make_campaign(target_temperature=0.9, target_max_tokens=1234)

        _run(engine.run_single_attack(campaign, AttackCategory.PROMPT_INJECTION, "hello"))

        (options,) = provider.chats
        assert isinstance(options, ChatOptions)
        assert options.temperature == 0.9
        assert options.max_tokens == 1234

    def test_retry_replays_identical_provider_options(self) -> None:
        """An activity retry replays the same input and re-creates the
        campaign from it; the same configured values must reproduce
        identical ChatOptions on every execution."""
        provider = _RecordingProvider()
        engine = _build_engine(provider)

        first = _run(
            engine.run_campaign(_make_campaign(target_temperature=0.7, target_max_tokens=4096))
        )
        second = _run(
            engine.run_campaign(_make_campaign(target_temperature=0.7, target_max_tokens=4096))
        )

        assert first.total_rounds == 2 and second.total_rounds == 2
        first_options = [(o.temperature, o.max_tokens) for o in provider.chats[:2]]
        second_options = [(o.temperature, o.max_tokens) for o in provider.chats[2:]]
        assert first_options == [(0.7, 4096), (0.7, 4096)]
        assert second_options == first_options


class TestAttackConfigurationToWorkflowInput:
    def test_create_config_round_trips_and_forwards_configured_values(self) -> None:
        from app.infrastructure.database.repositories.attack_run_repository import (
            _config_to_dict,
        )
        from app.infrastructure.database.repositories.attack_run_repository import (
            _dict_to_config as repo_config,
        )
        from app.redteam.application.handlers import _dict_to_config as api_config
        from app.redteam.temporal.activities import RedTeamWorkflowInput

        created = api_config(
            {
                "target_provider": "probe-provider",
                "target_model": "probe-model",
                "temperature": 0.7,
                "max_tokens": 4096,
                "categories": ["jailbreak"],
            }
        )
        hydrated = repo_config(_config_to_dict(created))
        assert hydrated.temperature == 0.7
        assert hydrated.max_tokens == 4096

        wf_input = RedTeamWorkflowInput(
            attack_run_id="run-1",
            target_provider=hydrated.target_provider,
            target_model=hydrated.target_model,
            target_temperature=hydrated.temperature,
            target_max_tokens=hydrated.max_tokens,
            attack_categories=tuple(c.value for c in hydrated.categories),
        )

        assert wf_input.target_temperature == 0.7
        assert wf_input.target_max_tokens == 4096
        assert wf_input.attack_categories == ("jailbreak",)

    def test_omitted_config_values_fall_back_to_domain_defaults(self) -> None:
        from app.redteam.application.handlers import _dict_to_config as api_config

        config = api_config({"target_provider": "probe-provider", "target_model": "probe-model"})
        assert config is not None
        assert config.temperature == 0.0
        assert config.max_tokens == 2048
