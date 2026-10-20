"""Focused Groq integration tests.

These are unit tests: the Groq HTTP transport is stubbed. They cover the
provider-specific wiring (endpoint, credential isolation, default model,
parameter compatibility, error identity, response/token mapping) plus its use
through the real ``JudgeEngine``. No live API request is made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import RateLimitError

from app.core.config import AppConfig
from app.evaluation.judge.domain import JudgeConfig, JudgeRequest
from app.evaluation.judge.engine import JudgeEngine
from app.providers.exceptions.base import ProviderException
from app.providers.exceptions.rate_limit import RateLimitExceeded
from app.providers.groq.constants import DEFAULT_BASE_URL, DEFAULT_MODEL
from app.providers.groq.provider import GroqProvider
from app.providers.models.messages import Message
from app.providers.models.options import ChatOptions

_FAKE_KEY = "gsk-unit-test-not-a-real-key"


def _sdk_response(
    *,
    content: str = "Hello from Groq",
    model: str = DEFAULT_MODEL,
    prompt_tokens: int = 11,
    completion_tokens: int = 7,
) -> MagicMock:
    """Create a mock OpenAI-compatible ChatCompletion (Groq wire shape)."""
    response = MagicMock()
    response.model = model
    response.id = "chatcmpl-groq-test"
    response.system_fingerprint = None

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = prompt_tokens + completion_tokens
    usage.prompt_tokens_details = None
    usage.completion_tokens_details = None
    response.usage = usage

    choice = MagicMock()
    choice.finish_reason = "stop"
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    choice.message = message
    response.choices = [choice]
    return response


def _http_response(status: int) -> MagicMock:
    """Create the mock httpx response OpenAI SDK errors require."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {}
    resp.request = MagicMock()
    resp.request.url = f"{DEFAULT_BASE_URL}/chat/completions"
    resp.content = b'{"error": {"message": "test"}}'
    return resp


def _provider(**kwargs: object) -> GroqProvider:
    return GroqProvider(api_key=_FAKE_KEY, **kwargs)  # type: ignore[arg-type]


class TestEndpointAndCredentials:
    """Endpoint, credential source, and startup behaviour."""

    def test_uses_groq_openai_compatible_endpoint(self) -> None:
        provider = _provider()
        sdk = provider._ensure_client()._client
        assert str(sdk.base_url).startswith(DEFAULT_BASE_URL)

    def test_explicit_key_is_injected(self) -> None:
        provider = _provider()
        assert provider._ensure_client()._client.api_key == _FAKE_KEY

    def test_groq_key_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "gsk-from-env")
        provider = GroqProvider()
        assert provider._ensure_client()._client.api_key == "gsk-from-env"

    def test_missing_key_is_configuration_error_at_request_time(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-must-not-be-used")
        provider = GroqProvider()  # construction/startup must not fail

        with pytest.raises(ProviderException) as excinfo:
            _run(provider.chat([Message.user("hi")]))

        exc = excinfo.value
        assert exc.error_code == "PROVIDER_CONFIGURATION_ERROR"
        assert "GROQ_API_KEY" in str(exc)
        assert "sk-openai-must-not-be-used" not in str(exc)
        assert exc.provider_name == "groq"

    @pytest.mark.asyncio
    async def test_health_without_key_is_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert await GroqProvider().health() is False


class TestModelSelection:
    """Default model configuration and request mapping."""

    def test_config_default_model(self) -> None:
        assert AppConfig(_env_file=None).groq_model == DEFAULT_MODEL

    def test_config_model_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
        assert AppConfig(_env_file=None).groq_model == "openai/gpt-oss-120b"

    @pytest.mark.asyncio
    async def test_default_model_used_when_omitted(self) -> None:
        provider = _provider(default_model="openai/gpt-oss-120b")
        create = AsyncMock(return_value=_sdk_response(model="openai/gpt-oss-120b"))
        provider._ensure_client()._client.chat.completions.create = create

        response = await provider.chat([Message.user("hi")])

        assert create.await_args.kwargs["model"] == "openai/gpt-oss-120b"
        assert response.model == "openai/gpt-oss-120b"

    @pytest.mark.asyncio
    async def test_explicit_model_wins_over_default(self) -> None:
        provider = _provider(default_model="openai/gpt-oss-120b")
        create = AsyncMock(return_value=_sdk_response(model="llama-3.1-8b-instant"))
        provider._ensure_client()._client.chat.completions.create = create

        await provider.chat([Message.user("hi")], model="llama-3.1-8b-instant")

        assert create.await_args.kwargs["model"] == "llama-3.1-8b-instant"


class TestRequestResponseAdaptation:
    """Messages/options are mapped and usage is surfaced with Groq identity."""

    @pytest.mark.asyncio
    async def test_response_and_token_usage_mapped(self) -> None:
        provider = _provider()
        create = AsyncMock(
            return_value=_sdk_response(
                content="Grounded answer",
                prompt_tokens=21,
                completion_tokens=5,
            ),
        )
        provider._ensure_client()._client.chat.completions.create = create

        response = await provider.chat(
            [Message.system("be brief"), Message.user("what is 2+2?")],
            options=ChatOptions(temperature=0.2, max_tokens=32),
        )

        request = create.await_args.kwargs
        assert request["model"] == DEFAULT_MODEL
        assert request["messages"][0] == {"role": "system", "content": "be brief"}
        assert request["messages"][1] == {"role": "user", "content": "what is 2+2?"}
        assert request["temperature"] == 0.2
        assert request["max_tokens"] == 32

        assert response.content == "Grounded answer"
        assert response.provider == "groq"
        assert response.usage.input_tokens == 21
        assert response.usage.output_tokens == 5
        assert response.usage.total_tokens == 26

    @pytest.mark.asyncio
    async def test_unsupported_logprobs_rejected_before_http_call(self) -> None:
        provider = _provider()
        create = AsyncMock()
        provider._ensure_client()._client.chat.completions.create = create

        with pytest.raises(ProviderException) as excinfo:
            await provider.chat(
                [Message.user("hi")],
                options=ChatOptions(logprobs=True),
            )

        assert excinfo.value.error_code == "PROVIDER_UNSUPPORTED_PARAMETER"
        assert "logprobs" in str(excinfo.value)
        create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_json_object_response_format_is_passed_through(self) -> None:
        provider = _provider()
        create = AsyncMock(return_value=_sdk_response(content='{"ok": true}'))
        provider._ensure_client()._client.chat.completions.create = create

        await provider.chat(
            [Message.user("return json")],
            options=ChatOptions(response_format={"type": "json_object"}),
        )

        assert create.await_args.kwargs["response_format"] == {"type": "json_object"}


class TestErrorMapping:
    """SDK errors are mapped and carry the Groq provider identity."""

    @pytest.mark.asyncio
    async def test_rate_limit_mapped_with_groq_provider_name(self) -> None:
        provider = _provider()
        error = RateLimitError(
            message="rate limited",
            response=_http_response(429),  # type: ignore[arg-type]
            body=None,
        )
        provider._ensure_client()._client.chat.completions.create = AsyncMock(
            side_effect=error,
        )

        with pytest.raises(RateLimitExceeded) as excinfo:
            await provider.chat([Message.user("hi")])

        assert excinfo.value.provider_name == "groq"
        assert str(excinfo.value) == "rate limited"


class TestEvaluationAndJudgeCompatibility:
    """The provider satisfies the judge's ChatProvider contract end to end."""

    @pytest.mark.asyncio
    async def test_judge_engine_scores_through_groq_provider(self) -> None:
        provider = _provider()
        provider._ensure_client()._client.chat.completions.create = AsyncMock(
            return_value=_sdk_response(
                content='{"score": 0.9, "confidence": 0.8, "reasoning": "supported"}',
                prompt_tokens=40,
                completion_tokens=12,
            ),
        )
        engine = JudgeEngine(
            default_provider=provider,
            default_config=JudgeConfig(model=DEFAULT_MODEL),
        )

        verdict = await engine.judge(
            JudgeRequest(
                metric_name="groundedness",
                prompt="What is the capital of France?",
                response="Paris",
                context="Paris is the capital of France.",
            ),
        )

        assert verdict.error is None
        assert verdict.score == pytest.approx(0.9)
        assert verdict.confidence == pytest.approx(0.8)
        assert verdict.tokens_input == 40
        assert verdict.tokens_output == 12
        assert verdict.judge_model == DEFAULT_MODEL


def _run(awaitable: object) -> object:
    """Run a coroutine without pytest-asyncio (for sync tests)."""
    import asyncio

    return asyncio.run(awaitable)  # type: ignore[arg-type]
