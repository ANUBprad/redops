"""Integration test for the evaluation runtime provider boundary.

Proves that ``execute_item_activity`` resolves the requested provider from the
shared ProviderRegistry and invokes its chat boundary, without requiring a
real LLM or a running Temporal server.
"""

from __future__ import annotations

import asyncio

from app.evaluation.temporal.activities import (
    ExecuteItemInput,
    configure_provider_registry,
    execute_item_activity,
)
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry


class FakeProvider:
    """Minimal provider that records invocation and returns a canned response."""

    provider_name = "openai"

    def __init__(self) -> None:
        self.called = False

    async def chat(self, messages, *, model: str, options=None) -> ChatResponse:
        self.called = True
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
