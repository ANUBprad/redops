"""Judge Engine — reusable LLM-as-judge infrastructure.

Provides a unified interface for calling LLM judges to evaluate
metric criteria. All LLM-based metrics delegate to this engine
rather than calling providers directly.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from app.evaluation.judge.domain import (
    JudgeConfig,
    JudgeRequest,
    JudgeResponse,
)
from app.evaluation.judge.prompts import (
    JUDGE_PROMPT_VERSION,
    SCORE_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    build_metric_description,
    build_rubric_text,
)

if TYPE_CHECKING:
    from app.providers.contracts.chat import ChatProvider

logger = logging.getLogger(__name__)


class JudgeEngine:
    """Reusable LLM-as-judge engine.

    Accepts a JudgeRequest and produces a JudgeResponse by:
    1. Building a judge prompt from templates
    2. Calling the LLM provider
    3. Parsing the structured JSON response
    4. Returning a typed JudgeResponse
    """

    def __init__(
        self,
        default_provider: ChatProvider | None = None,
        default_config: JudgeConfig | None = None,
    ) -> None:
        """Initialize the judge engine."""
        self._default_provider = default_provider
        self._default_config = default_config or JudgeConfig()

    async def judge(
        self,
        request: JudgeRequest,
        provider: ChatProvider | None = None,
        config: JudgeConfig | None = None,
    ) -> JudgeResponse:
        """Execute a judge evaluation.

        Args:
            request: The judge request containing metric, prompt, response, etc.
            provider: Override provider for this call.
            config: Override config for this call.

        Returns:
            A JudgeResponse with score, confidence, reasoning.

        """
        effective_provider = provider or self._default_provider
        if effective_provider is None:
            msg = "No provider available for judge evaluation"
            raise RuntimeError(msg)

        effective_config = config or request.config or self._default_config

        prompt = self._build_prompt(request)

        start = time.monotonic()
        try:
            raw_output, usage = await self._call_llm(
                effective_provider,
                prompt,
                effective_config,
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.exception("Judge LLM call failed")
            return JudgeResponse(
                score=0.0,
                confidence=0.0,
                reasoning=f"Judge LLM call failed: {exc}",
                rubric_version=request.rubric.version
                if request.rubric
                else effective_config.rubric_version,
                judge_model=effective_config.model,
                judge_prompt_version=JUDGE_PROMPT_VERSION,
                execution_time_ms=elapsed,
                error=f"Judge LLM call failed: {exc}",
            )

        elapsed = int((time.monotonic() - start) * 1000)

        parsed, parse_error = self._parse_response(raw_output)
        rubric_version = (
            request.rubric.version if request.rubric else effective_config.rubric_version
        )

        if parse_error is not None:
            return JudgeResponse(
                score=0.0,
                confidence=0.0,
                reasoning=parse_error,
                rubric_version=rubric_version,
                judge_model=effective_config.model,
                judge_prompt_version=JUDGE_PROMPT_VERSION,
                raw_output=raw_output,
                execution_time_ms=elapsed,
                tokens_input=usage.get("tokens_input", 0),
                tokens_output=usage.get("tokens_output", 0),
                error=parse_error,
            )

        return JudgeResponse(
            score=parsed["score"],
            confidence=parsed["confidence"],
            reasoning=parsed["reasoning"],
            rubric_version=rubric_version,
            judge_model=effective_config.model,
            judge_prompt_version=JUDGE_PROMPT_VERSION,
            raw_output=raw_output,
            execution_time_ms=elapsed,
            cost_usd=self._estimate_cost(effective_provider, effective_config, usage),
            tokens_input=usage.get("tokens_input", 0),
            tokens_output=usage.get("tokens_output", 0),
        )

    def _build_prompt(self, request: JudgeRequest) -> str:
        """Build the judge prompt from request data."""
        rubric_text = build_rubric_text(request.metric_name)
        if request.rubric:
            rubric_text = "\n".join(
                f"{e.score} = {e.label}: {e.description}" for e in request.rubric.entries
            )

        return SCORE_PROMPT_TEMPLATE.format(
            metric_name=request.metric_name,
            metric_description=build_metric_description(request.metric_name),
            rubric_text=rubric_text,
            prompt=request.prompt,
            response=request.response,
            context=request.context or "No context provided.",
            reference=request.reference or "No reference answer provided.",
        )

    async def _call_llm(
        self,
        provider: ChatProvider,
        prompt: str,
        config: JudgeConfig,
    ) -> tuple[str, dict[str, Any]]:
        """Call the LLM provider with the judge prompt.

        Returns:
            Tuple of (response_content, usage_info) where usage_info
            contains tokens_input, tokens_output.

        """
        from app.providers.models.messages import Message
        from app.providers.models.options import ChatOptions

        messages = [
            Message.system(SYSTEM_PROMPT),
            Message.user(prompt),
        ]

        options = ChatOptions(
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        response = await provider.chat(
            messages,
            model=config.model,
            options=options,
        )

        usage_info: dict[str, Any] = {
            "tokens_input": response.usage.input_tokens,
            "tokens_output": response.usage.output_tokens,
        }

        return response.content, usage_info

    def _parse_response(self, raw_output: str) -> tuple[dict[str, Any], str | None]:
        """Parse the LLM response into structured fields.

        Returns:
            Tuple of (parsed fields, parse error). The error is None
            only when the output is a JSON object carrying numeric
            score and confidence fields. Malformed output never
            produces a fabricated default score.

        """
        text = raw_output.strip()

        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if not json_match:
            return {}, "Judge returned no parsable JSON object"

        try:
            parsed = json.loads(json_match.group())
        except json.JSONDecodeError:
            return {}, "Judge returned malformed JSON"

        if not isinstance(parsed, dict):
            return {}, "Judge output was not a JSON object"

        try:
            score = float(parsed["score"])
            confidence = float(parsed["confidence"])
        except (KeyError, TypeError, ValueError):
            return {}, "Judge output missing numeric 'score' or 'confidence'"

        reasoning = parsed.get("reasoning", "No reasoning provided")
        if not isinstance(reasoning, str):
            reasoning = str(reasoning)

        return (
            {
                "score": max(0.0, min(1.0, score)),
                "confidence": max(0.0, min(1.0, confidence)),
                "reasoning": reasoning,
            },
            None,
        )

    def _estimate_cost(
        self,
        provider: ChatProvider,
        config: JudgeConfig,
        usage: dict[str, Any],
    ) -> float:
        """Estimate the judge call cost from token usage.

        Unknown provider/model pricing yields 0.0 — the judge call
        still succeeded; only accounting is unavailable.

        """
        from app.providers.cost.defaults import build_default_cost_calculator
        from app.providers.tokenization.usage import TokenUsage

        provider_name = getattr(provider, "provider_name", "")
        model_id = config.model
        if not provider_name or not model_id:
            return 0.0

        calculator = build_default_cost_calculator()
        try:
            return calculator.estimate_cost(
                provider_name,
                model_id,
                TokenUsage(
                    input_tokens=int(usage.get("tokens_input", 0)),
                    output_tokens=int(usage.get("tokens_output", 0)),
                ),
            )
        except KeyError:
            return 0.0
