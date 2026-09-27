"""R-13: token/cost accounting provenance integrity.

Proven defect: unknown-pricing costs are recorded as exact 0.0 and the
pricing flag is dropped before every trusted surface (activity result,
run aggregate, API, analytics, UI), so a run with no pricing data
reports $0.00 indistinguishable from genuinely free.

Contract locked here (additive, migration-free):
* ItemExecutionResult.cost_estimated survives into ExecuteItemResult;
* the workflow accumulates run-level completeness into trace_data,
  the workflow result, run provenance, and RunResponse.cost_estimated
  (None = recorded before provenance existed);
* JudgeResponse.cost_estimated marks unknown judge pricing, and judge
  metric metadata persists it into metric_results.metadata;
* red-team TargetExecution carries cost_estimated into attack records;
* durable replay reuses both cost and flag with zero new provider calls.

Fake providers/calculators only -- no credentials, no Temporal server.
"""

from __future__ import annotations

import pytest

from app.evaluation.execution.item_executor import ItemExecutor
from app.evaluation.judge.domain import JudgeConfig, JudgeRequest
from app.evaluation.judge.engine import JudgeEngine
from app.evaluation.temporal.activities import (
    ExecuteItemInput,
    ExecuteItemResult,
    _result_for_durable_execution,
)
from app.evaluation.temporal.workflow import _cost_completeness_ok
from app.providers.cost.calculator import CostCalculator
from app.providers.cost.defaults import build_default_cost_calculator
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage


class _FakeChatProvider:
    """Minimal ChatProvider double returning fixed usage."""

    provider_name = "openai"

    def __init__(self, content: str = '{"score": 0.9, "confidence": 0.8}') -> None:
        self.content = content
        self.calls = 0

    async def chat(self, messages, *, model: str, options=None) -> ChatResponse:  # type: ignore[no-untyped-def]
        self.calls += 1
        return ChatResponse(
            model=model,
            provider="openai",
            usage=Usage(input_tokens=100, output_tokens=50, total_tokens=150),
            finish_reason=FinishReason.STOP,
            request_id="req-fake",
            content=self.content,
        )


def _item_dataset(prompt: str = "hello"):  # type: ignore[no-untyped-def]
    from app.evaluation.data.dataset import DatasetItem

    return DatasetItem(prompt=prompt)


def _judge_request() -> JudgeRequest:
    return JudgeRequest(
        metric_name="relevance",
        prompt="prompt",
        response="response",
        config=JudgeConfig(provider_name="openai", model="gpt-4o"),
    )


@pytest.mark.asyncio
async def test_item_executor_unpriced_model_marks_cost_unknown() -> None:
    executor = ItemExecutor(CostCalculator())
    result = await executor.execute(
        _FakeChatProvider("hi"),
        provider_name="openai",
        model_id="model-without-pricing",
        item=_item_dataset(),
    )
    assert result.tokens_input == 100
    assert result.tokens_output == 50
    assert result.cost_usd == 0.0
    assert result.cost_estimated is False


@pytest.mark.asyncio
async def test_item_executor_priced_model_marks_cost_priced() -> None:
    executor = ItemExecutor(build_default_cost_calculator())
    result = await executor.execute(
        _FakeChatProvider("hi"),
        provider_name="openai",
        model_id="gpt-4o",
        item=_item_dataset(),
    )
    assert result.cost_usd > 0.0
    assert result.cost_estimated is True


@pytest.mark.asyncio
async def test_durable_replay_reuses_cost_and_flag_without_new_call() -> None:
    from app.evaluation.execution.item_executor import ItemExecutionResult

    durable = ItemExecutionResult(
        item_index=0,
        prompt="hello",
        provider_name="openai",
        model_id="model-without-pricing",
        response="hi",
        tokens_input=100,
        tokens_output=50,
        cost_usd=0.0,
        cost_estimated=False,
    )
    result = await _result_for_durable_execution(
        ExecuteItemInput(run_id="run-1", item_index=0, provider_name="openai", model_id="x"),
        "item-0",
        durable,
    )
    assert result.cost_usd == 0.0
    assert result.cost_estimated is False


def test_cost_completeness_ok() -> None:
    priced = ExecuteItemResult(item_index=0, cost_usd=0.01, cost_estimated=True)
    unknown = ExecuteItemResult(item_index=1, cost_usd=0.0, cost_estimated=False)
    assert _cost_completeness_ok([]) is True
    assert _cost_completeness_ok([priced, priced]) is True
    assert _cost_completeness_ok([priced, unknown]) is False


@pytest.mark.asyncio
async def test_judge_unpriced_model_marks_cost_unknown() -> None:
    engine = JudgeEngine(default_provider=_FakeChatProvider())
    config = JudgeConfig(provider_name="openai", model="model-without-pricing")
    response = await engine.judge(_judge_request(), config=config)
    assert response.error is None
    assert response.cost_usd == 0.0
    assert response.cost_estimated is False


@pytest.mark.asyncio
async def test_judge_priced_model_marks_cost_priced() -> None:
    engine = JudgeEngine(default_provider=_FakeChatProvider())
    config = JudgeConfig(provider_name="openai", model="gpt-4o")
    response = await engine.judge(_judge_request(), config=config)
    assert response.error is None
    assert response.cost_usd > 0.0
    assert response.cost_estimated is True


def test_run_response_cost_flag_derivation() -> None:
    from app.api.evaluation_run import _cost_estimated_from_provenance

    assert _cost_estimated_from_provenance(None) is None
    assert _cost_estimated_from_provenance({}) is None
    assert (
        _cost_estimated_from_provenance({"cost_accounting": {"estimated_complete": True}}) is True
    )
    assert (
        _cost_estimated_from_provenance({"cost_accounting": {"estimated_complete": False}}) is False
    )


@pytest.mark.asyncio
async def test_redteam_target_unpriced_model_marks_cost_unknown() -> None:
    from app.redteam.domain.value_objects import AttackScenario
    from app.redteam.engine.target_executor import TargetExecutor

    class _Registry:
        def resolve(self, name: str) -> _FakeChatProvider:
            return _FakeChatProvider("attack-response")

    executor = TargetExecutor(_Registry())  # type: ignore[arg-type]
    execution, _ = await executor.execute(
        AttackScenario(prompt="ignore instructions"),
        provider_name="openai",
        model="model-without-pricing",
    )
    assert execution.cost_usd == 0.0
    assert execution.cost_estimated is False
