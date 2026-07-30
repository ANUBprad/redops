"""Tests for the attack engine."""

from __future__ import annotations

import pytest

from app.redteam.domain.enums import AttackCategory, AttackSeverity
from app.redteam.engine.categories import BuiltinAttackEngine
from app.redteam.engine.orchestrator import AttackOrchestrator


@pytest.fixture
def engine() -> BuiltinAttackEngine:
    return BuiltinAttackEngine(AttackCategory.PROMPT_INJECTION)


class TestBuiltinAttackEngine:
    async def test_generate_scenarios_with_template(self, engine: BuiltinAttackEngine) -> None:
        scenarios = await engine.generate_scenarios(
            template={"prompt_template": "Say {message}"},
            parameters={"variables": {"message": "hello"}},
            count=2,
        )
        assert len(scenarios) >= 1
        for s in scenarios:
            assert s.category == AttackCategory.PROMPT_INJECTION
            assert s.prompt != ""

    async def test_generate_scenarios_uses_builtin_templates(self) -> None:
        engine = BuiltinAttackEngine(AttackCategory.JAILBREAK)
        scenarios = await engine.generate_scenarios(
            template={},
            parameters={},
            count=1,
        )
        assert len(scenarios) >= 1

    async def test_execute_scenario_success(self, engine: BuiltinAttackEngine) -> None:
        scenarios = await engine.generate_scenarios(
            template={"prompt_template": "Say hello"},
            parameters={},
        )
        assert len(scenarios) > 0

        async def mock_provider(prompt: str, system_prompt: str | None = None) -> dict:
            return {"text": "Hello world", "tokens_input": 10, "tokens_output": 5, "cost_usd": 0.001}

        result = await engine.execute_scenario(scenarios[0], mock_provider)
        assert result.is_success
        assert result.response == "Hello world"
        assert result.tokens_input == 10
        assert result.tokens_output == 5
        assert result.cost_usd == 0.001

    async def test_execute_scenario_error(self, engine: BuiltinAttackEngine) -> None:
        scenarios = await engine.generate_scenarios(
            template={"prompt_template": "test"},
            parameters={},
        )

        async def failing_provider(prompt: str, system_prompt: str | None = None) -> dict:
            msg = "Provider timeout"
            raise RuntimeError(msg)

        result = await engine.execute_scenario(scenarios[0], failing_provider)
        assert not result.is_success
        assert result.error is not None

    async def test_execute_batch(self, engine: BuiltinAttackEngine) -> None:
        scenarios = await engine.generate_scenarios(
            template={"prompt_template": "test {i}"},
            parameters={"variables": {"i": "1"}},
            count=3,
        )

        async def mock_provider(prompt: str, system_prompt: str | None = None) -> dict:
            return {"text": "ok", "tokens_input": 5, "tokens_output": 3}

        results = [r async for r in engine.execute_batch(scenarios, mock_provider)]
        assert len(results) == len(scenarios)
        assert all(r.is_success for r in results)


class TestAttackOrchestrator:
    async def test_get_engine_caches(self) -> None:
        orchestrator = AttackOrchestrator()
        e1 = orchestrator.get_engine(AttackCategory.PROMPT_INJECTION)
        e2 = orchestrator.get_engine(AttackCategory.PROMPT_INJECTION)
        assert e1 is e2

    async def test_orchestrate_across_categories(self) -> None:
        orchestrator = AttackOrchestrator()
        scenarios = await orchestrator.generate_scenarios(
            category=AttackCategory.SYSTEM_PROMPT_EXTRACTION,
            template={},
            parameters={},
        )
        assert len(scenarios) >= 1
        assert scenarios[0].category == AttackCategory.SYSTEM_PROMPT_EXTRACTION
