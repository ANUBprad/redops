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
                reasoning=f"Judge call failed: {exc}",
                rubric_version=request.rubric.version
                if request.rubric
                else effective_config.rubric_version,
                judge_model=effective_config.model,
                judge_prompt_version=JUDGE_PROMPT_VERSION,
                execution_time_ms=elapsed,
            )

        elapsed = int((time.monotonic() - start) * 1000)

        parsed = self._parse_response(raw_output)

        rubric_version = (
            request.rubric.version if request.rubric else effective_config.rubric_version
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
            cost_usd=usage.get("cost_usd", 0.0),
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

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        """Parse the LLM response into structured fields."""
        text = raw_output.strip()

        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return {
                    "score": max(0.0, min(1.0, float(parsed.get("score", 0.0)))),
                    "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.0)))),
                    "reasoning": str(parsed.get("reasoning", "No reasoning provided")),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        score = self._extract_score_fallback(text)
        return {
            "score": score,
            "confidence": 0.5,
            "reasoning": text[:500] if text else "Failed to parse judge response",
        }

    def _extract_score_fallback(self, text: str) -> float:
        """Extract a score from unstructured text as fallback."""
        patterns = [
            r"score[:\s]*(\d+\.?\d*)",
            r"rating[:\s]*(\d+\.?\d*)",
            r"(\d+\.?\d*)\s*/\s*1",
            r"(\d+\.?\d*)\s*out of\s*1",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    val = float(match.group(1))
                    if 0.0 <= val <= 1.0:
                        return val
                    if 0.0 <= val <= 10.0:
                        return val / 10.0
                except ValueError:
                    continue
        return 0.0
