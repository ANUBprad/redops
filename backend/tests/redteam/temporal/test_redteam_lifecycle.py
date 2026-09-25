"""End-to-end red team lifecycle tests on the real Temporal workflow.

Runs RedTeamWorkflow + red_team_campaign_activity on a time-skipping
WorkflowEnvironment with an in-memory SQLite DB and a coordinated fake
provider. Proves:

- F3  RUNNING -> COMPLETED on a successful campaign
- F1  signal("cancel") -> the workflow returns a "cancelled" verdict and
      stops dispatching further provider work
- F4  a run already CANCELLED (endpoint race) is never pushed to COMPLETED;
      the finalize guard preserves the terminal state
- F5  progress counters reflect only genuinely completed rounds
- persistence: campaign JSON + metric rows only for completed rounds

Note on the test environment: unlike a real Temporal server, the
time-skipping env cancels a TRY_CANCEL activity task with an asyncio
CancelledError rather than cooperatively flipping ``activity.is_cancelled()``
for the spin to observe, so the DB transition to CANCELLED is tested via the
endpoint-race path while cooperative-observation behavior is proven at the
engine unit level (see test_campaign_cancellation.py).
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from temporalio import activity
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.redteam.domain.entities import AttackRun
from app.redteam.domain.enums import AttackStatus
from app.redteam.domain.value_objects import AttackConfiguration
from app.redteam.temporal.activities import (
    RedTeamWorkflowInput,
    configure_redteam_metric_engine,
    configure_redteam_provider_registry,
    configure_redteam_session_factory,
    red_team_campaign_activity,
)
from app.redteam.temporal.workflow import RedTeamWorkflow

# A response that trips keyword-based LEAKED across many safety dimensions so
# effectiveness lands at 1.0 (>= 0.8 threshold) and the loop stops on round 1.
VIOLATION_TEXT = (
    "ignore previous instructions bypass override policy circumvent illegal "
    "unethical prohibited; kill bomb destroy weapon violence injure torture "
    "abuse; credit card password secret api key credential; sudo admin exec "
    "eval delete drop table rm -rf"
)

# A compliant non-policy response: keyword scoring stays low, effectiveness <
# threshold, so the loop keeps iterating instead of stopping early.
SAFE_TEXT = "I will not comply with that request."


class _EmptyMetricEngine:
    """No-op metric engine so the campaign loop does not depend on LLM metrics."""

    def resolve_metrics(self, names: Any) -> list[Any]:
        return []

    async def evaluate_batch(self, resolved: Any, metric_input: Any) -> list[Any]:
        return []


class _CoordinatedProvider:
    """Fake provider whose chat can park until cancellation is observed.

    ``park_on_call`` >= 1 parks every chat call at or after that index,
    first at a gate Event (so the test can signal deterministically) and
    then in a spin loop until ``activity.is_cancelled()`` is True (so no
    work continues past a quietly-delivered cancellation).
    """

    provider_name = "test-provider"

    def __init__(self, *, park_on_call: int | None = None, content: str = SAFE_TEXT) -> None:
        self.chat_calls = 0
        self.park_on_call = park_on_call
        self.content = content
        self.entered = threading.Event()
        self.gate = threading.Event()
        self.error: Exception | None = None

    async def chat(self, messages: Any, *, model: str, options: Any = None) -> ChatResponse:
        self.chat_calls += 1
        if self.error is not None:
            raise self.error
        if self.park_on_call is not None and self.chat_calls >= self.park_on_call:
            self.entered.set()
            while not self.gate.is_set():
                await asyncio.sleep(0.01)
            # Wait for cooperative cancellation. Bounded: if the environment
            # hard-cancels the activity task instead of flipping the flag,
            # this await raises CancelledError — that is expected and the
            # workflow-level contract (result.status == "cancelled") still
            # holds without a DB transition.
            deadline = time.monotonic() + 12.0
            while not activity.is_cancelled() and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
        return ChatResponse(
            content=self.content,
            model=model,
            provider=self.provider_name,
            usage=Usage(input_tokens=4, output_tokens=2),
            finish_reason=FinishReason.STOP,
        )

    async def health(self) -> bool:
        return True

    def capabilities(self) -> Any:
        return object()


async def _build_factory() -> async_sessionmaker[Any]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            ([AttackRunModel.__table__, MetricResultModel.__table__]),
        )
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_running_run(factory: async_sessionmaker[Any]) -> AttackRun:
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        config = AttackConfiguration(
            target_provider="test-provider",
            target_model="m",
        )
        run = AttackRun.create(configuration=config)
        run.queue()
        run.start(total_items=3)
        await repo.save(run)
        await session.commit()
        return run


async def _load_run(factory: async_sessionmaker[Any], run_id: Any) -> AttackRun | None:
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        return await repo.find_by_id(run_id)


async def _await_flag(flag: threading.Event, *, timeout: float = 15.0) -> None:
    """Poll a thread-safe flag from the async test loop (loop-agnostic)."""
    deadline = time.monotonic() + timeout
    while not flag.is_set():
        if time.monotonic() >= deadline:
            raise AssertionError("flag never set within timeout")
        await asyncio.sleep(0.02)


async def _wait_status(
    factory: async_sessionmaker[Any],
    run_id: Any,
    expected: AttackStatus,
    *,
    timeout: float = 15.0,
) -> AttackRun:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = await _load_run(factory, run_id)
        if run is not None and run.status == expected:
            return run
        await asyncio.sleep(0.05)
    raise AssertionError(
        f"run never reached {expected.value} (last status: {run.status if run else None})"
    )


async def _metric_count(factory: async_sessionmaker[Any], run_id: str) -> int:
    async with factory() as session:
        rows = await session.scalars(
            select(MetricResultModel).where(MetricResultModel.run_id == run_id)
        )
        return sum(1 for _ in rows)


def _workflow_input(run_id: str) -> RedTeamWorkflowInput:
    return RedTeamWorkflowInput(
        attack_run_id=run_id,
        target_provider="test-provider",
        target_model="m",
        max_rounds=3,
        max_attacks=3,
        effectiveness_threshold=0.8,
    )


class _LifecycleHarness:
    """Wires activity globals, a registry, and a worker around the environment."""

    def __init__(self, env: WorkflowEnvironment, factory: async_sessionmaker[Any]) -> None:
        self.env = env
        self.factory = factory
        self.provider: _CoordinatedProvider | None = None

    @property
    def client(self) -> Client:
        return self.env.client

    async def __aenter__(self) -> _LifecycleHarness:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        pass


@pytest.fixture
async def time_skipping_env():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


async def _run_workflow(
    env: WorkflowEnvironment,
    *,
    workflow_id: str,
    input: RedTeamWorkflowInput,
    provider: _CoordinatedProvider,
    factory: async_sessionmaker[Any],
) -> Any:
    import app.redteam.temporal.activities as mod

    registry = ProviderRegistry()
    registry.register(provider)

    old_registry = mod._provider_registry
    old_metric = mod._metric_engine
    old_session = mod._session_factory
    try:
        configure_redteam_provider_registry(registry)
        configure_redteam_metric_engine(_EmptyMetricEngine())
        configure_redteam_session_factory(factory)

        async with Worker(
            env.client,
            task_queue="red-team-q",
            workflows=[RedTeamWorkflow],
            activities=[red_team_campaign_activity],
        ):
            result = await env.client.execute_workflow(
                RedTeamWorkflow.run,
                input,
                id=workflow_id,
                task_queue="red-team-q",
            )
            return result
    finally:
        mod._provider_registry = old_registry
        mod._metric_engine = old_metric
        mod._session_factory = old_session


class TestWorkflowLifecycle:
    async def test_successful_campaign_completes_run(self, time_skipping_env) -> None:
        factory = await _build_factory()
        run = await _create_running_run(factory)
        provider = _CoordinatedProvider(park_on_call=None, content=VIOLATION_TEXT)

        result = await _run_workflow(
            time_skipping_env,
            workflow_id=f"red-team-wf-{run.id}",
            input=_workflow_input(str(run.id)),
            provider=provider,
            factory=factory,
        )

        assert result.status == "completed"
        completed = await _wait_status(factory, run.id, AttackStatus.COMPLETED)
        assert completed.items_completed == 1
        assert completed.items_violated == 1
        assert completed.campaign_results["state"] == "completed"
        assert len(completed.campaign_results["rounds"]) == 1
        assert await _metric_count(factory, str(run.id)) == 1

    async def test_cancel_signal_returns_cancelled_workflow(self, time_skipping_env) -> None:
        """signal("cancel") -> the workflow stops; no further provider work runs."""
        factory = await _build_factory()
        run = await _create_running_run(factory)
        provider = _CoordinatedProvider(park_on_call=1)
        workflow_id = f"red-team-wf-{run.id}"

        workflow_task = asyncio.create_task(
            _run_workflow(
                time_skipping_env,
                workflow_id=workflow_id,
                input=_workflow_input(str(run.id)),
                provider=provider,
                factory=factory,
            )
        )

        await _await_flag(provider.entered)
        await time_skipping_env.client.get_workflow_handle(workflow_id).signal("cancel")
        provider.gate.set()

        result = await asyncio.wait_for(workflow_task, timeout=30)
        # F1: the workflow stops waiting on the signalled cancellation once the
        # activity is interrupted (TRY_CANCEL), returning a cancelled verdict.
        assert result.status == "cancelled"
        # The round-1 target call was in flight; the judge and every further
        # round never ran. No post-cancellation work was performed.
        assert provider.chat_calls == 1

        await asyncio.sleep(3)
        run_after = await _load_run(factory, run.id)
        assert run_after is not None
        # F4: the run must never be pushed to COMPLETED by this cancellation.
        assert run_after.status != AttackStatus.COMPLETED

    async def test_cancelled_run_is_never_completed(self, time_skipping_env) -> None:
        """Endpoint race: DB says CANCELLED before the workflow starts (F4).

        The activity finishes its campaign but finalization must leave the
        terminal CANCELLED state alone — campaign JSON and metric rows are
        still attached, but the run is never COMPLETED.
        """
        factory = await _build_factory()
        run = await _create_running_run(factory)
        # Endpoint side races ahead: DB is CANCELLED before the workflow starts.
        run.cancel()
        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            await repo.save(run)
            await session.commit()

        provider = _CoordinatedProvider(park_on_call=None)
        workflow_id = f"red-team-wf-{run.id}"

        workflow_task = asyncio.create_task(
            _run_workflow(
                time_skipping_env,
                workflow_id=workflow_id,
                input=_workflow_input(str(run.id)),
                provider=provider,
                factory=factory,
            )
        )

        result = await asyncio.wait_for(workflow_task, timeout=45)
        # The workflow itself was not cancelled; its verdict reflects the
        # campaign's terminal state.
        assert result.status == "budget_exhausted"
        await asyncio.sleep(2)

        final = await _load_run(factory, run.id)
        assert final is not None
        assert final.status == AttackStatus.CANCELLED
        assert final.campaign_results is not None
        assert final.campaign_results["state"] == "budget_exhausted"
        # The not-RUNNING finalize path records no run-level counters.
        assert final.items_completed == 0
        # Per-round metric rows for the completed rounds are still persisted
        # (3 safe rounds, one canonical semantic row each).
        assert await _metric_count(factory, str(run.id)) == 3
