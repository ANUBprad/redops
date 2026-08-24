"""Target executor — routes attack prompts to AI providers via ProviderRegistry.

Sends attack scenarios to target models through the standard
ProviderRegistry → ChatProvider.chat() path and returns structured
execution records.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.providers.models.messages import Message
from app.providers.models.options import ChatOptions
from app.redteam.domain.campaign import TargetExecution
from app.redteam.domain.value_objects import AttackResult, AttackScenario

if TYPE_CHECKING:
    from app.providers.registry.registry import ProviderRegistry


class TargetExecutor:
    """Executes attack scenarios against target models via ProviderRegistry.

    Wraps the ProviderRegistry and translates between red-team domain
    objects and the standard provider contract.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        scenario: AttackScenario,
        *,
        provider_name: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> tuple[TargetExecution, AttackResult]:
        """Execute a single attack scenario against the target model.

        Returns both the raw TargetExecution record and a
        domain-level AttackResult for downstream evaluation.
        """
        provider = self._registry.resolve(provider_name)

        messages: list[Message] = []
        if scenario.system_prompt_override:
            messages.append(Message.system(scenario.system_prompt_override))
        messages.append(Message.user(scenario.prompt))

        options = ChatOptions(
            temperature=temperature,
            max_tokens=max_tokens,
        )

        start = time.monotonic()
        try:
            response = await provider.chat(  # type: ignore[attr-defined]
                messages,
                model=model,
                options=options,
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            execution = TargetExecution(
                attack_prompt=scenario.prompt,
                system_prompt=scenario.system_prompt_override,
                target_response=response.content,
                tokens_input=response.usage.input_tokens,
                tokens_output=response.usage.output_tokens,
                total_tokens=response.usage.total_tokens,
                cost_usd=0.0,
                latency_ms=latency_ms,
                provider_name=provider_name,
                model_name=model,
            )

            attack_result = AttackResult(
                scenario=scenario,
                response=response.content,
                execution_time_ms=latency_ms,
                tokens_input=response.usage.input_tokens,
                tokens_output=response.usage.output_tokens,
            )

            return execution, attack_result

        except Exception as exc:
            latency_ms = int((time.monotonic() - start) * 1000)
            execution = TargetExecution(
                attack_prompt=scenario.prompt,
                system_prompt=scenario.system_prompt_override,
                target_response="",
                latency_ms=latency_ms,
                provider_name=provider_name,
                model_name=model,
                error=str(exc),
            )
            attack_result = AttackResult(
                scenario=scenario,
                response="",
                execution_time_ms=latency_ms,
                error=str(exc),
            )
            return execution, attack_result

    async def execute_batch(
        self,
        scenarios: list[AttackScenario],
        *,
        provider_name: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> list[tuple[TargetExecution, AttackResult]]:
        """Execute multiple scenarios sequentially."""
        results = []
        for scenario in scenarios:
            result = await self.execute(
                scenario,
                provider_name=provider_name,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            results.append(result)
        return results
