"""Opt-in smoke tests that prove configured providers reach their real APIs.

These tests are skipped unless REDOPS_LIVE_PROVIDER_TESTS=1 and the provider's
API key is available. They intentionally use a tiny response budget; never put
provider responses or credentials in test output.
"""

from __future__ import annotations

import os

import pytest

from app.providers.anthropic.provider import AnthropicProvider
from app.providers.groq.provider import GroqProvider
from app.providers.models.messages import Message
from app.providers.models.options import ChatOptions
from app.providers.openai.provider import OpenAIProvider


def _live_configuration(key_name: str, model_name: str, default_model: str) -> tuple[str, str]:
    if os.getenv("REDOPS_LIVE_PROVIDER_TESTS") != "1":
        pytest.skip("Set REDOPS_LIVE_PROVIDER_TESTS=1 to opt into billable live API tests")

    api_key = os.getenv(key_name, "").strip()
    if not api_key:
        pytest.skip(f"{key_name} is not configured; live provider call was not attempted")

    model = os.getenv(model_name, "").strip() or default_model
    if not model:
        pytest.fail(f"{model_name} must name a live model")

    return api_key, model


async def _assert_live_chat(provider: object, model: str) -> None:
    try:
        await provider.initialize()  # type: ignore[attr-defined]
        response = await provider.chat(  # type: ignore[attr-defined]
            [Message.user("Reply with the exact token REDOPS_LIVE_SMOKE_OK.")],
            model=model,
            options=ChatOptions(temperature=0.0, max_tokens=24, timeout_seconds=30.0),
        )
        assert isinstance(response.content, str) and response.content.strip()
        assert response.usage.total_tokens > 0
        assert response.usage.input_tokens >= 0
        assert response.usage.output_tokens > 0
    finally:
        await provider.dispose()  # type: ignore[attr-defined]


async def test_live_openai_chat() -> None:
    api_key, model = _live_configuration(
        "OPENAI_API_KEY", "REDOPS_LIVE_OPENAI_MODEL", "gpt-4o-mini"
    )
    await _assert_live_chat(OpenAIProvider(api_key=api_key), model)


async def test_live_anthropic_chat() -> None:
    api_key, model = _live_configuration(
        "ANTHROPIC_API_KEY", "REDOPS_LIVE_ANTHROPIC_MODEL", "claude-sonnet-4-20250514"
    )
    await _assert_live_chat(AnthropicProvider(api_key=api_key), model)


async def test_live_groq_chat() -> None:
    api_key, model = _live_configuration(
        "GROQ_API_KEY", "REDOPS_LIVE_GROQ_MODEL", "llama-3.3-70b-versatile"
    )
    await _assert_live_chat(GroqProvider(api_key=api_key), model)
