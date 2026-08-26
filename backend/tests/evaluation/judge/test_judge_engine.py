"""Hardening tests for the JudgeEngine.

The judge must never fabricate scores: provider failures and
malformed output surface as explicit errors, structured output is
validated before acceptance, and token usage/cost are accounted.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.evaluation.judge.domain import JudgeConfig, JudgeRequest
from app.evaluation.judge.engine import JudgeEngine
from app.providers.models.enums import FinishReason
from app.providers.models.messages import Message
from app.providers.models.responses import ChatResponse, Usage


class ScriptedChatProvider:
    """Chat provider returning a canned body (or raising)."""

    def __init__(self, content: str | Exception, provider_name: str = "scripted") -> None:
        self._content = content
        self._provider_name = provider_name
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str = "",
        options: Any = None,
    ) -> ChatResponse:
        self.calls += 1
        if isinstance(self._content, Exception):
            raise self._content
        return ChatResponse(
            content=self._content,
            model=model or "judge-model",
            provider=self._provider_name,
            usage=Usage(input_tokens=100, output_tokens=50, total_tokens=150),
            finish_reason=FinishReason.STOP,
        )


def _request() -> JudgeRequest:
    return JudgeRequest(
        metric_name="correctness",
        prompt="What is the capital of France?",
        response="Paris",
        reference="Paris",
    )


class TestProviderFailures:
    """Provider failures must be explicit errors, not zero scores."""

    @pytest.mark.asyncio
    async def test_llm_failure_sets_error(self) -> None:
        provider = ScriptedChatProvider(RuntimeError("connection refused"))
        engine = JudgeEngine(default_provider=provider)

        response = await engine.judge(_request())

        assert response.error is not None
        assert "connection refused" in response.error
        assert response.score == 0.0
        assert response.confidence == 0.0

    @pytest.mark.asyncio
    async def test_no_provider_is_explicit_error(self) -> None:
        engine = JudgeEngine(default_provider=None)

        with pytest.raises(RuntimeError):
            await engine.judge(_request())


class TestMalformedOutput:
    """Malformed judge output must never become a default score."""

    @pytest.mark.asyncio
    async def test_plain_text_output_is_error(self) -> None:
        provider = ScriptedChatProvider("Score: 0.9 out of 1 because reasons")
        engine = JudgeEngine(default_provider=provider)

        response = await engine.judge(_request())

        assert response.error is not None
        assert "JSON" in response.error

    @pytest.mark.asyncio
    async def test_broken_json_is_error(self) -> None:
        provider = ScriptedChatProvider('{"score": 0.9, "confidence"')
        engine = JudgeEngine(default_provider=provider)

        response = await engine.judge(_request())

        assert response.error is not None
        assert response.raw_output  # raw output preserved for debugging

    @pytest.mark.asyncio
    async def test_missing_score_field_is_error(self) -> None:
        provider = ScriptedChatProvider(
            json.dumps({"confidence": 0.8, "reasoning": "no score given"}),
        )
        engine = JudgeEngine(default_provider=provider)

        response = await engine.judge(_request())

        assert response.error is not None
        assert "score" in (response.error or "")


class TestValidOutput:
    """Well-formed verdicts parse into validated fields."""

    @pytest.mark.asyncio
    async def test_valid_verdict_parsed(self) -> None:
        provider = ScriptedChatProvider(
            json.dumps({"score": 0.85, "confidence": 0.9, "reasoning": "solid"}),
        )
        engine = JudgeEngine(default_provider=provider, default_config=JudgeConfig(model="gpt-4o"))

        response = await engine.judge(_request())

        assert response.error is None
        assert response.score == pytest.approx(0.85)
        assert response.confidence == pytest.approx(0.9)
        assert response.reasoning == "solid"
        assert response.judge_model == "gpt-4o"
        assert response.tokens_input == 100
        assert response.tokens_output == 50

    @pytest.mark.asyncio
    async def test_out_of_range_values_clamped(self) -> None:
        provider = ScriptedChatProvider(
            json.dumps({"score": 1.7, "confidence": -0.2, "reasoning": "overconfident"}),
        )
        engine = JudgeEngine(default_provider=provider)

        response = await engine.judge(_request())

        assert response.error is None
        assert response.score == 1.0
        assert response.confidence == 0.0

    @pytest.mark.asyncio
    async def test_json_embedded_in_prose_accepted(self) -> None:
        provider = ScriptedChatProvider(
            'Verdict: {"score": 0.6, "confidence": 0.7, "reasoning": "ok"} hope this helps',
        )
        engine = JudgeEngine(default_provider=provider)

        response = await engine.judge(_request())

        assert response.error is None
        assert response.score == pytest.approx(0.6)


class TestCostAccounting:
    """Judge calls account for token usage and estimated cost."""

    @pytest.mark.asyncio
    async def test_cost_computed_for_known_pricing(self) -> None:
        provider = ScriptedChatProvider(
            json.dumps({"score": 0.5, "confidence": 0.5, "reasoning": "m"}),
            provider_name="openai",
        )
        engine = JudgeEngine(
            default_provider=provider,
            default_config=JudgeConfig(provider_name="openai", model="gpt-4o"),
        )

        response = await engine.judge(_request())

        assert response.cost_usd > 0.0

    @pytest.mark.asyncio
    async def test_unknown_pricing_yields_zero_without_failure(self) -> None:
        provider = ScriptedChatProvider(
            json.dumps({"score": 0.5, "confidence": 0.5, "reasoning": "m"}),
        )
        engine = JudgeEngine(
            default_provider=provider,
            default_config=JudgeConfig(provider_name="unknown", model="nope"),
        )

        response = await engine.judge(_request())

        assert response.error is None
        assert response.cost_usd == 0.0
