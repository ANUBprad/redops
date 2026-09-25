"""Integration test for the evaluation runtime provider boundary.

Proves that ``execute_item_activity`` resolves the requested provider from the
shared ProviderRegistry and invokes its chat boundary, without requiring a
real LLM or a running Temporal server.
"""

from __future__ import annotations

import asyncio

from app.evaluation.temporal.activities import (
    ExecuteItemInput,
    ExecuteItemResult,
    configure_provider_registry,
    execute_item_activity,
)
from app.providers.models.options import ChatOptions
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry


class FakeProvider:
    """Minimal provider that records invocation and returns a canned response."""

    provider_name = "openai"

    def __init__(self) -> None:
        self.called = False
        self.last_options: ChatOptions | None = None

    async def chat(
        self, messages, *, model: str, options: ChatOptions | None = None
    ) -> ChatResponse:
        self.called = True
        self.last_options = options
        return ChatResponse(
            model=model,
            provider="openai",
            usage=Usage(input_tokens=10, output_tokens=5),
            content="hello from fake provider",
        )


def test_runtime_resolves_and_invokes_provider() -> None:
    registry = ProviderRegistry()
    fake = FakeProvider()
    registry.register(fake)
    configure_provider_registry(registry)

    result = asyncio.run(
        execute_item_activity(
            ExecuteItemInput(
                run_id="run-1",
                item_index=0,
                provider_name="openai",
                model_id="gpt-4o",
                prompt="hi",
                prompt_template="{prompt}",
            )
        )
    )

    assert result.failed is False
    assert result.response == "hello from fake provider"
    assert result.tokens_input == 10
    assert result.tokens_output == 5
    assert fake.called is True


def _run_item(input: ExecuteItemInput) -> tuple[FakeProvider, ExecuteItemResult]:
    """Run the item activity against a recording fake provider."""
    registry = ProviderRegistry()
    fake = FakeProvider()
    registry.register(fake)
    configure_provider_registry(registry)
    result = asyncio.run(execute_item_activity(input))
    return fake, result


def test_configured_generation_parameters_reach_provider_chat() -> None:
    """P4-B: configured temperature/max_tokens are forwarded to provider.chat."""
    fake, result = _run_item(
        ExecuteItemInput(
            run_id="run-2",
            item_index=0,
            provider_name="openai",
            model_id="gpt-4o",
            prompt="hi",
            prompt_template="{prompt}",
            temperature=0.7,
            max_tokens=128,
        )
    )

    assert result.failed is False
    assert fake.last_options is not None
    assert fake.last_options.temperature == 0.7
    assert fake.last_options.max_tokens == 128


def test_omitted_generation_parameters_default_to_none() -> None:
    """P4-B: omitted temperature/max_tokens stay None so provider defaults apply."""
    fake, result = _run_item(
        ExecuteItemInput(
            run_id="run-3",
            item_index=0,
            provider_name="openai",
            model_id="gpt-4o",
            prompt="hi",
            prompt_template="{prompt}",
        )
    )

    assert result.failed is False
    assert fake.last_options is not None
    assert fake.last_options.temperature is None
    assert fake.last_options.max_tokens is None
