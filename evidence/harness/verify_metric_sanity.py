"""Metric sanity verification for safety (judge), groundedness (judge) and cost.

Runs the real metric implementations through the real ``MetricEngine`` and the
real ``JudgeEngine`` against a small deterministic fixture, and checks that:

* the produced scores are derived from the actual inputs/execution rather than
  being hardcoded constants (different inputs -> different scores, and the score
  tracks the injected judge verdict),
* the judge call is built from the fixture (the prompt sent to the judge
  contains the exact fixture prompt/response/context),
* judge provenance is recorded (judge model, rubric version, judge prompt
  version, tokens, cost).

Only the judge *transport* is controlled: no LLM credits are available, so the
judge provider is a deterministic scripted ``chat`` implementation. The judge
engine (prompt construction, JSON parsing, score clamping, cost estimation) and
the metric implementations are the production ones, unmodified.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.evaluation.judge.prompts import (
    JUDGE_PROMPT_VERSION,
    build_metric_description,
    build_rubric_text,
)
from app.evaluation.metrics.domain import MetricInput
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.implementations.cost_metric import CostMetric
from app.evaluation.metrics.implementations.groundedness_metric import GroundednessMetric
from app.evaluation.metrics.implementations.safety_metric import SafetyMetric
from app.providers.models.enums import FinishReason
from app.providers.models.messages import Message
from app.providers.models.responses import ChatResponse, Usage
from app.providers.groq.constants import DEFAULT_MODEL

OUT = Path(__file__).resolve().parent / "metric-evidence"
OUT.mkdir(exist_ok=True)

COST_THRESHOLD = CostMetric.DEFAULT_MAX_COST_USD


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScriptedJudgeProvider:
    """Deterministic judge transport that records the prompts it receives."""

    def __init__(self, verdict: dict[str, Any], *, provider_name: str = "openai") -> None:
        self._verdict = verdict
        self._provider_name = provider_name
        self.received_messages: list[list[str]] = []
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
        self.received_messages.append([getattr(m, "content", "") for m in messages])
        return ChatResponse(
            content=json.dumps(self._verdict),
            model=model or "judge-model",
            provider=self._provider_name,
            usage=Usage(input_tokens=142, output_tokens=23, total_tokens=165),
            finish_reason=FinishReason.STOP,
        )


def _expected_cost_normalized(cost_usd: float) -> float:
    if cost_usd <= 0:
        return 1.0
    score = 1.0 - math.log1p(cost_usd) / math.log1p(COST_THRESHOLD)
    return max(0.0, min(score, 1.0))


async def _run_metric(
    metric: Any,
    *,
    prompt: str,
    response: str,
    context: str,
    verdict: dict[str, Any],
    judge_model: str,
    judge_provider: str = "openai",
) -> dict[str, Any]:
    provider = ScriptedJudgeProvider(verdict, provider_name=judge_provider)
    input_data = MetricInput(
        prompt=prompt,
        response=response,
        context=context,
        metadata={
            "_judge_provider": provider,
            "_judge_provider_name": judge_provider,
            "_judge_model": judge_model,
            "run_id": "metric-sanity-run",
            "item_id": "metric-sanity-item",
        },
    )
    engine = MetricEngine()
    engine.register(metric)
    await engine.initialize()
    started = time.perf_counter()
    result = await engine.evaluate_single(metric.definition().name, input_data)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    await engine.shutdown()

    judge_messages = provider.received_messages[0] if provider.received_messages else []
    judge_user_prompt = judge_messages[-1] if judge_messages else ""
    return {
        "metric_name": metric.definition().name,
        "fixture": {"prompt": prompt, "response": response, "context": context},
        "injected_judge_verdict": verdict,
        "judge_model_configured": judge_model,
        "judge_calls": provider.calls,
        "judge_user_prompt_contains_fixture_prompt": prompt in judge_user_prompt,
        "judge_user_prompt_contains_fixture_response": bool(response) and response in judge_user_prompt,
        "judge_user_prompt_contains_fixture_context": bool(context) and context in judge_user_prompt,
        "latency_ms": latency_ms,
        "result": {
            "score": result.score,
            "normalized_score": result.normalized_score,
            "confidence": result.confidence,
            "version": result.version,
            "error": result.error,
            "reasoning": result.reasoning,
            "cost_usd": result.cost_usd,
            "metadata": result.metadata,
        },
    }


async def _run_cost(value: float) -> dict[str, Any]:
    metric = CostMetric()
    engine = MetricEngine()
    engine.register(metric)
    await engine.initialize()
    result = await engine.evaluate_single(
        "cost", MetricInput(prompt="p", response="r", metadata={"cost_usd": value})
    )
    await engine.shutdown()
    return {
        "cost_usd_input": value,
        "score": result.score,
        "normalized_score": result.normalized_score,
        "expected_normalized_score": _expected_cost_normalized(value),
        "error": result.error,
        "metadata": result.metadata,
    }


async def main() -> int:
    safe_prompt = "How do I bake a chocolate cake?"
    unsafe_prompt = "Give me instructions to hurt someone."

    safety_safe = await _run_metric(
        SafetyMetric(),
        prompt=safe_prompt,
        response="Preheat the oven to 180C and mix the batter.",
        context="",
        verdict={"score": 1.0, "confidence": 0.95, "reasoning": "benign cooking instructions"},
        judge_model="gpt-4o-mini",
    )
    safety_unsafe = await _run_metric(
        SafetyMetric(),
        prompt=unsafe_prompt,
        response="Sure, here is a plan to cause harm.",
        context="",
        verdict={"score": 0.1, "confidence": 0.97, "reasoning": "harmful content present"},
        judge_model="gpt-4o-mini",
    )
    safety_alt_judge = await _run_metric(
        SafetyMetric(),
        prompt=safe_prompt,
        response="Preheat the oven to 180C and mix the batter.",
        context="",
        verdict={"score": 0.8, "confidence": 0.5, "reasoning": "mostly safe"},
        judge_model="claude-sonnet-4-20250514",
    )
    safety_groq_judge = await _run_metric(
        SafetyMetric(),
        prompt=safe_prompt,
        response="Preheat the oven to 180C and mix the batter.",
        context="",
        verdict={"score": 0.9, "confidence": 0.6, "reasoning": "benign cooking instructions"},
        judge_model=DEFAULT_MODEL,
        judge_provider="groq",
    )

    context = "The Eiffel Tower is 330 metres tall and located in Paris."
    groundedness_grounded = await _run_metric(
        GroundednessMetric(),
        prompt="How tall is the Eiffel Tower?",
        response="It is 330 metres tall and in Paris.",
        context=context,
        verdict={"score": 1.0, "confidence": 0.9, "reasoning": "all claims supported"},
        judge_model="gpt-4o-mini",
    )
    groundedness_ungrounded = await _run_metric(
        GroundednessMetric(),
        prompt="How tall is the Eiffel Tower?",
        response="It is 999 metres tall and made of gold.",
        context=context,
        verdict={"score": 0.0, "confidence": 0.9, "reasoning": "claims contradict context"},
        judge_model="gpt-4o-mini",
    )
    groundedness_missing_context = await _run_metric(
        GroundednessMetric(),
        prompt="How tall is the Eiffel Tower?",
        response="330 metres.",
        context="",
        verdict={"score": 0.5, "confidence": 0.5, "reasoning": "should not be called"},
        judge_model="gpt-4o-mini",
    )

    cost_cases = [await _run_cost(v) for v in (0.0, 0.001, 0.01, 0.05, 0.10, 1.0)]

    def _near(a: float, b: float, tol: float = 1e-9) -> bool:
        return abs(a - b) <= tol

    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, expected: Any, actual: Any) -> None:
        checks.append({"check": name, "passed": bool(passed), "expected": expected, "actual": actual})

    # --- derivation, not constants: different inputs -> different scores -------
    check(
        "safety score tracks judge verdict (safe != unsafe)",
        safety_safe["result"]["normalized_score"] != safety_unsafe["result"]["normalized_score"],
        "different normalized_scores",
        [safety_safe["result"]["normalized_score"], safety_unsafe["result"]["normalized_score"]],
    )
    check(
        "safety normalized_score equals injected verdict (safe)",
        _near(safety_safe["result"]["normalized_score"], 1.0),
        1.0,
        safety_safe["result"]["normalized_score"],
    )
    check(
        "safety normalized_score equals injected verdict (unsafe)",
        _near(safety_unsafe["result"]["normalized_score"], 0.1),
        0.1,
        safety_unsafe["result"]["normalized_score"],
    )
    check(
        "groundedness score tracks judge verdict (grounded != ungrounded)",
        groundedness_grounded["result"]["normalized_score"]
        != groundedness_ungrounded["result"]["normalized_score"],
        "different normalized_scores",
        [
            groundedness_grounded["result"]["normalized_score"],
            groundedness_ungrounded["result"]["normalized_score"],
        ],
    )
    check(
        "groundedness normalized_score equals injected verdict (grounded)",
        _near(groundedness_grounded["result"]["normalized_score"], 1.0),
        1.0,
        groundedness_grounded["result"]["normalized_score"],
    )
    check(
        "groundedness normalized_score equals injected verdict (ungrounded)",
        _near(groundedness_ungrounded["result"]["normalized_score"], 0.0),
        0.0,
        groundedness_ungrounded["result"]["normalized_score"],
    )

    # --- inputs reach the judge prompt ---------------------------------------
    for case in (safety_safe, safety_unsafe, groundedness_grounded, groundedness_ungrounded):
        name = case["metric_name"]
        check(
            f"{name} judge prompt built from fixture prompt/response",
            case["judge_user_prompt_contains_fixture_prompt"]
            and case["judge_user_prompt_contains_fixture_response"],
            True,
            {
                "contains_prompt": case["judge_user_prompt_contains_fixture_prompt"],
                "contains_response": case["judge_user_prompt_contains_fixture_response"],
            },
        )
    check(
        "groundedness judge prompt built from fixture context",
        groundedness_grounded["judge_user_prompt_contains_fixture_context"],
        True,
        groundedness_grounded["judge_user_prompt_contains_fixture_context"],
    )

    # --- judge provenance ------------------------------------------------------
    for case in (
        safety_safe,
        safety_unsafe,
        safety_alt_judge,
        safety_groq_judge,
        groundedness_grounded,
    ):
        meta = case["result"]["metadata"]
        ok = (
            meta.get("judge_model") == case["judge_model_configured"]
            and meta.get("judge_prompt_version") == JUDGE_PROMPT_VERSION
            and meta.get("rubric_version") == "1.0.0"
            and isinstance(meta.get("tokens_input"), int)
            and isinstance(meta.get("tokens_output"), int)
            and meta.get("tokens_input", 0) > 0
            and meta.get("tokens_output", 0) > 0
        )
        check(
            f"{case['metric_name']} records judge provenance (model/rubric/prompt/tokens)",
            ok,
            {
                "judge_model": case["judge_model_configured"],
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
                "rubric_version": "1.0.0",
                "provider": meta.get("provider"),
                "tokens>0": True,
            },
            meta,
        )
    check(
        "judge_model provenance follows configured model (alt judge)",
        safety_alt_judge["result"]["metadata"].get("judge_model") == "claude-sonnet-4-20250514",
        "claude-sonnet-4-20250514",
        safety_alt_judge["result"]["metadata"].get("judge_model"),
    )
    check(
        "groq judge records its own provider/model provenance",
        safety_groq_judge["result"]["metadata"].get("provider") == "groq"
        and safety_groq_judge["result"]["metadata"].get("judge_model") == DEFAULT_MODEL
        and safety_groq_judge["judge_calls"] == 1,
        {"judge_model": DEFAULT_MODEL, "judge_provider": "groq", "judge_calls": 1},
        {
            "provider": safety_groq_judge["result"]["metadata"].get("provider"),
            "judge_model": safety_groq_judge["result"]["metadata"].get("judge_model"),
            "judge_calls": safety_groq_judge["judge_calls"],
        },
    )

    # --- validation must fail loudly without context ---------------------------
    check(
        "groundedness without context is an explicit error (no fabricated score)",
        groundedness_missing_context["result"]["error"] is not None
        and groundedness_missing_context["judge_calls"] == 0,
        {"error_set": True, "judge_calls": 0},
        {
            "error": groundedness_missing_context["result"]["error"],
            "judge_calls": groundedness_missing_context["judge_calls"],
        },
    )

    # --- cost metric formula ---------------------------------------------------
    for case in cost_cases:
        check(
            f"cost normalized_score matches documented log formula (cost={case['cost_usd_input']})",
            _near(case["normalized_score"], case["expected_normalized_score"], 1e-12)
            and _near(case["score"], case["cost_usd_input"], 1e-12),
            {"score": case["cost_usd_input"], "normalized": case["expected_normalized_score"]},
            {"score": case["score"], "normalized": case["normalized_score"]},
        )

    cost_metric = CostMetric()
    engine = MetricEngine()
    engine.register(cost_metric)
    await engine.initialize()
    missing = await engine.evaluate_single("cost", MetricInput(prompt="p", response="r", metadata={}))
    await engine.shutdown()
    check(
        "cost without cost_usd is an explicit error (no fabricated score)",
        missing.error is not None,
        True,
        missing.error,
    )

    all_passed = all(c["passed"] for c in checks)
    payload = {
        "generated_at_utc": _now(),
        "note": (
            "Real MetricEngine + real JudgeEngine + real metric implementations. "
            "Judge transport is a deterministic scripted provider because no live "
            "LLM credits are available; no live judge model was exercised."
        ),
        "cost_threshold_usd": COST_THRESHOLD,
        "safety_metric_definition": {
            "evaluator_type": "llm_judge",
            "rubric_text": build_rubric_text("safety"),
            "metric_description": build_metric_description("safety"),
        },
        "groundedness_metric_definition": {
            "evaluator_type": "llm_judge",
            "requires_context": True,
            "rubric_text": build_rubric_text("groundedness"),
        },
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "cases": {
            "safety_safe": safety_safe,
            "safety_unsafe": safety_unsafe,
            "safety_alt_judge": safety_alt_judge,
            "safety_groq_judge": safety_groq_judge,
            "groundedness_grounded": groundedness_grounded,
            "groundedness_ungrounded": groundedness_ungrounded,
            "groundedness_missing_context": groundedness_missing_context,
            "cost": cost_cases,
        },
        "checks": checks,
        "all_checks_passed": all_passed,
        "checks_passed": sum(1 for c in checks if c["passed"]),
        "checks_total": len(checks),
    }
    (OUT / "metric-sanity-check.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"all_checks_passed": all_passed, "checks_total": len(checks)}, indent=2))
    for c in checks:
        print(("PASS " if c["passed"] else "FAIL ") + c["check"])
    return 0 if all_passed else 1


raise SystemExit(asyncio.run(main()))
