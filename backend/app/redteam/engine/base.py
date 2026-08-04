"""Base attack engine — Strategy pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from app.redteam.domain.value_objects import AttackResult, AttackScenario

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class AttackEngine(ABC):
    """Strategy interface for executing attack categories."""

    @abstractmethod
    async def generate_scenarios(
        self,
        template: dict[str, Any],
        parameters: dict[str, Any],
        *,
        count: int = 1,
    ) -> list[AttackScenario]:
        """Generate attack scenarios from a template."""
        ...

    @abstractmethod
    async def execute_scenario(
        self,
        scenario: AttackScenario,
        provider_callable: Any,
    ) -> AttackResult:
        """Execute a single scenario against a target."""
        ...

    @abstractmethod
    async def execute_batch(
        self,
        scenarios: list[AttackScenario],
        provider_callable: Any,
    ) -> AsyncIterator[AttackResult]:
        """Execute multiple scenarios, yielding results as they complete."""
        ...


class BaseAttackEngine(ABC):
    """Base implementation with common utilities."""

    @staticmethod
    def substitute_variables(template: str, variables: dict[str, str]) -> str:
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", value)
        return result

    @staticmethod
    def build_prompt(
        prompt_template: str,
        variables: dict[str, str] | None = None,
        system_prompt_override: str | None = None,
    ) -> tuple[str, str | None]:
        prompt = prompt_template
        if variables:
            prompt = BaseAttackEngine.substitute_variables(prompt, variables)
        return prompt, system_prompt_override
