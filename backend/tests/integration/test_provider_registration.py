"""Tests for provider registry wiring via the existing provider architecture.

These tests prove that OpenAI/Anthropic/Groq are registered through the
shared ProviderRegistry when their credentials are configured, that missing
credentials do not crash startup (and instead surface a clear configuration
error at run validation), and that exactly one registry is used by the
evaluation execution path.
"""

from __future__ import annotations

import pytest

from app.core.config import AppConfig
from app.evaluation.orchestration.executor import ProviderInvocationStage
from app.evaluation.temporal import activities as eval_activities
from app.infrastructure.composition.container import InfrastructureContainer
from app.providers.anthropic.provider import AnthropicProvider
from app.providers.groq.provider import GroqProvider
from app.providers.openai.provider import OpenAIProvider
from app.providers.registry.registry import ProviderRegistry
from app.providers.runtime.execution.runtime_coordinator import RuntimeCoordinator


def _build_registry(
    openai_key: str = "",
    anthropic_key: str = "",
    groq_key: str = "",
) -> ProviderRegistry:
    # AppConfig honors env *aliases* (OPENAI_API_KEY / ANTHROPIC_API_KEY /
    # GROQ_API_KEY), not field names, so pass the aliases explicitly.
    cfg = AppConfig(
        OPENAI_API_KEY=openai_key,
        ANTHROPIC_API_KEY=anthropic_key,
        GROQ_API_KEY=groq_key,
    )
    container = InfrastructureContainer(cfg)
    registry = ProviderRegistry()
    container._register_providers(registry)
    return registry


def test_openai_registered_when_key_present() -> None:
    registry = _build_registry(openai_key="sk-test-openai")
    assert registry.is_registered("openai")
    assert isinstance(registry.resolve("openai"), OpenAIProvider)


def test_anthropic_registered_when_key_present() -> None:
    registry = _build_registry(anthropic_key="sk-test-anthropic")
    assert registry.is_registered("anthropic")
    assert isinstance(registry.resolve("anthropic"), AnthropicProvider)


def test_groq_registered_when_key_present() -> None:
    registry = _build_registry(groq_key="gsk-test-groq")
    assert registry.is_registered("groq")
    assert isinstance(registry.resolve("groq"), GroqProvider)


def test_both_registered_when_keys_present() -> None:
    registry = _build_registry(openai_key="sk-openai", anthropic_key="sk-ant")
    assert registry.count() == 2
    assert isinstance(registry.resolve("openai"), OpenAIProvider)
    assert isinstance(registry.resolve("anthropic"), AnthropicProvider)


def test_all_three_registered_when_all_keys_present() -> None:
    registry = _build_registry(
        openai_key="sk-openai",
        anthropic_key="sk-ant",
        groq_key="gsk-groq",
    )
    assert registry.count() == 3
    assert isinstance(registry.resolve("groq"), GroqProvider)


def test_missing_groq_key_yields_clear_configuration_error() -> None:
    # GROQ_API_KEY unset: startup succeeds but a run selecting "groq" must
    # fail validation with an explicit configuration error, not a crash.
    registry = _build_registry()
    assert not registry.is_registered("groq")

    from app.evaluation.execution.context.context import PipelineContext, ProviderSelection

    ctx = PipelineContext(
        run_id="test-run",
        provider_selection=ProviderSelection(provider_name="groq", model_id="llama-3.3-70b-versatile"),
    )
    stage = ProviderInvocationStage(registry, RuntimeCoordinator())
    issues = stage.validate(ctx)
    assert len(issues) == 1
    assert issues[0].code == "PROVIDER_NOT_FOUND"
    assert "groq" in issues[0].message


def test_missing_credentials_do_not_crash_startup() -> None:
    # No keys configured: registration is simply skipped, startup proceeds.
    registry = _build_registry()
    assert registry.count() == 0


def test_unknown_provider_raises_existing_error() -> None:
    registry = ProviderRegistry()
    registry.register(OpenAIProvider(api_key="sk-test-openai"))
    with pytest.raises(KeyError, match="not registered"):
        registry.resolve("anthropic")


def test_exactly_one_runtime_registry_used_by_execution_path() -> None:
    registry = ProviderRegistry()
    registry.register(OpenAIProvider(api_key="sk-test-openai"))
    eval_activities.configure_provider_registry(registry)
    assert eval_activities._provider_registry is registry
