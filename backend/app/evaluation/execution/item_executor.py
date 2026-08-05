"""Item executor — real provider invocation for a single evaluation item.

Builds the prompt for a dataset item, calls the configured chat
provider, and returns a fully-annotated result including real
token usage, estimated cost, and latency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.evaluation.execution.prompt_builder import PromptTemplate
from app.providers.cost.calculator import CostCalculator

if TYPE_CHECKING:
    from app.evaluation.data.dataset import DatasetItem
    from app.providers.contracts.chat import ChatProvider
    from app.providers.models.options import ChatOptions
    from app.providers.models.responses import ChatResponse, Usage

__all__ = [
    "ItemExecutionResult",
    "ItemExecutor",
]


@dataclass(frozen=True, slots=True)
class ItemExecutionResult:
    """The outcome of executing one dataset item against a provider.

    Attributes:
        item_index: Zero-based index of the item in the dataset.
        prompt: The exact prompt text sent to the provider.
        provider_name: Provider identifier.
        model_id: Model identifier.
        response: The model's response text.
        reference: Optional reference answer from the item.
        context: Optional context from the item.
        tokens_input: Input tokens reported by the provider.
        tokens_output: Output tokens reported by the provider.
        tokens_cached: Cached input tokens reported by the provider.
        cost_usd: Estimated cost in USD (0.0 when pricing is unknown).
        cost_estimated: False when no pricing model was registered.
        latency_ms: Wall-clock latency of the provider call.
        finish_reason: Provider finish reason string.
        request_id: Provider request ID, if reported.
        failed: True when the provider call raised.
        error: Error message when failed.

    """

    item_index: int
    prompt: str
    provider_name: str
    model_id: str
    response: str = ""
    reference: str | None = None
    context: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cached: int = 0
    cost_usd: float = 0.0
    cost_estimated: bool = True
    latency_ms: int = 0
    finish_reason: str = "unknown"
    request_id: str | None = None
    failed: bool = False
    error: str | None = None

    @property
    def is_success(self) -> bool:
        """Return True when the provider call succeeded."""
        return not self.failed

    def to_metric_metadata(self) -> dict[str, Any]:
        """Return metadata consumed by metric evaluators.

        Returns:
            A dict with cost, latency, token, and provider fields.

        """
        return {
            "cost_usd": self.cost_usd,
            "cost_estimated": self.cost_estimated,
            "latency_ms": self.latency_ms,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_cached": self.tokens_cached,
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "request_id": self.request_id or "",
            "finish_reason": self.finish_reason,
        }


class ItemExecutor:
    """Executes dataset items against a chat provider.

    Usage:
        executor = ItemExecutor(cost_calculator, prompt_template)
        result = await executor.execute(provider, "openai", "gpt-4o", item, index=0)
    """

    def __init__(
        self,
        cost_calculator: CostCalculator,
        prompt_template: PromptTemplate | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            cost_calculator: Calculator used to estimate real USD costs.
            prompt_template: Template used to build messages; defaults
                to sending the raw item prompt.

        """
        self._cost_calculator = cost_calculator
        self._prompt_template = prompt_template or PromptTemplate(template="{prompt}")

    async def execute(
        self,
        provider: ChatProvider,
        *,
        provider_name: str,
        model_id: str,
        item: DatasetItem,
        item_index: int = 0,
        options: ChatOptions | None = None,
    ) -> ItemExecutionResult:
        """Execute a single dataset item.

        Args:
            provider: The chat provider to invoke.
            provider_name: Provider identifier used for cost lookup.
            model_id: Model identifier used for the call and cost lookup.
            item: The dataset item to evaluate.
            item_index: Zero-based item index.
            options: Optional chat options.

        Returns:
            An ItemExecutionResult.

        """
        messages = self._prompt_template.build_messages(item)
        start = time.monotonic()
        try:
            response: ChatResponse = await provider.chat(
                messages,
                model=model_id,
                options=options,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return ItemExecutionResult(
                item_index=item_index,
                prompt=self._prompt_template.render(item),
                provider_name=provider_name,
                model_id=model_id,
                reference=item.reference,
                context=item.context,
                latency_ms=elapsed_ms,
                failed=True,
                error=str(exc),
            )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return self._to_result(
            item=item,
            item_index=item_index,
            provider_name=provider_name,
            model_id=model_id,
            response=response,
            latency_ms=elapsed_ms,
        )

    def _to_result(
        self,
        *,
        item: DatasetItem,
        item_index: int,
        provider_name: str,
        model_id: str,
        response: ChatResponse,
        latency_ms: int,
    ) -> ItemExecutionResult:
        """Build a success result from a provider response."""
        usage: Usage = response.usage
        cost_usd, cost_estimated = self._estimate_cost(
            provider_name=provider_name,
            model_id=model_id,
            usage=usage,
        )
        finish_reason = getattr(response, "finish_reason", None)
        return ItemExecutionResult(
            item_index=item_index,
            prompt=self._prompt_template.render(item),
            provider_name=provider_name,
            model_id=model_id,
            response=response.content,
            reference=item.reference,
            context=item.context,
            tokens_input=usage.input_tokens,
            tokens_output=usage.output_tokens,
            tokens_cached=usage.cached_tokens,
            cost_usd=cost_usd,
            cost_estimated=cost_estimated,
            latency_ms=latency_ms,
            finish_reason=str(finish_reason.value if finish_reason is not None else "unknown"),
            request_id=response.request_id,
        )

    def _estimate_cost(
        self,
        *,
        provider_name: str,
        model_id: str,
        usage: Usage,
    ) -> tuple[float, bool]:
        """Estimate cost for a request using the cost calculator.

        Args:
            provider_name: Provider identifier.
            model_id: Model identifier.
            usage: Token usage for the request.

        Returns:
            A tuple of (estimated cost in USD, pricing found flag).

        """
        try:
            from app.providers.tokenization.usage import TokenUsage

            cost = self._cost_calculator.estimate_cost(
                provider_name,
                model_id,
                TokenUsage(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cached_tokens=usage.cached_tokens,
                    audio_tokens=usage.audio_tokens,
                ),
            )
            return max(cost, 0.0), True
        except KeyError:
            return 0.0, False
