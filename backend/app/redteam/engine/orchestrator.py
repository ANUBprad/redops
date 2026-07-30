"""Attack engine orchestrator — selects and delegates to the right strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.redteam.domain.enums import AttackCategory
from app.redteam.engine.categories import BuiltinAttackEngine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.redteam.domain.value_objects import AttackResult, AttackScenario


class AttackOrchestrator:
    """Selects the appropriate engine for a given category and executes attacks."""

    def __init__(self) -> None:
        self._engines: dict[AttackCategory, BuiltinAttackEngine] = {}

    def get_engine(self, category: AttackCategory) -> BuiltinAttackEngine:
        if category not in self._engines:
            self._engines[category] = BuiltinAttackEngine(category)
        return self._engines[category]

    async def generate_scenarios(
        self,
        category: AttackCategory,
        template: dict[str, Any],
        parameters: dict[str, Any],
        *,
        count: int = 1,
    ) -> list[AttackScenario]:
        engine = self.get_engine(category)
        return await engine.generate_scenarios(template, parameters, count=count)

    async def execute_scenario(
        self,
        scenario: AttackScenario,
        provider_callable: Any,
    ) -> AttackResult:
        engine = self.get_engine(scenario.category)
        return await engine.execute_scenario(scenario, provider_callable)

    async def execute_batch(
        self,
        scenarios: list[AttackScenario],
        provider_callable: Any,
    ) -> AsyncIterator[AttackResult]:
        if not scenarios:
            return
        engine = self.get_engine(scenarios[0].category)
        async for result in engine.execute_batch(scenarios, provider_callable):
            yield result
