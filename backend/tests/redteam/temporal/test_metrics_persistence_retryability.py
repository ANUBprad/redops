"""P6-C5 tests: F7 metric/result persistence failure is retryable and truthful.

A persistence failure during the metric_results phase (which happens AFTER
all provider calls have produced results) must NOT:

    1. Be swallowed into a FAILED return value â€” the already-paid provider
       result would be silently dropped.
    2. Leave the run COMPLETED before the metric rows are durable.

Instead it must propagate as a retryable error so Temporal retries, and the
retry must re-persist the SAME already-produced provider results WITHOUT
re-invoking any provider (durable round resume, P6-C2/C3).

Using only deterministic fake providers (no real credentials).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.models.red_team_round import RedTeamRoundModel
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.redteam.domain.entities import AttackRun
from app.redteam.domain.enums import AttackStatus
from app.redteam.engine.campaign_engine import _MetricPersistenceError
from app.redteam.temporal import activities as redteam_activities
from app.redteam.temporal.activities import (
    RedTeamWorkflowInput,
    configure_redteam_metric_engine,
    configure_redteam_provider_registry,
    configure_redteam_session_factory,
    red_team_campaign_activity,
)

TARGET_PROVIDER = "openai"
TARGET_MODEL = "gpt-4"

_REDTEAM_ACTIVITY_GLOBALS = (
    "_provider_registry",
    "_metric_engine",
    "_session_factory",
)


def _fake_judge_payload() -> dict[str, Any]:
    return {
        "verdict": "SUCCESS",
        "score": 0.95,
        "confidence": 0.9,
        "reasoning": "deterministic reasoning",
        "evidence": "deterministic evidence",
    }


def _fake_registry_provider(
    target_content: str,
    judge_payload: dict[str, Any],
) -> tuple[MagicMock, AsyncMock]:
    """Return (registry, provider) for a single-round campaign.

    The provider serves the target call, then the semantic judge call.
    A retry that re-invokes providers would exhaust the side_effect list
    and fail loudly â€” so a passing retry proves no provider re-invoke.
    """
    from app.providers.models.enums import FinishReason
    from app.providers.models.responses import ChatResponse, Usage

    provider = AsyncMock()
    provider.provider_name = TARGET_PROVIDER
    provider.chat.side_effect = [
        ChatResponse(
            content=target_content,
            model=TARGET_MODEL,
            provider=TARGET_PROVIDER,
            usage=Usage(input_tokens=10, output_tokens=5),
            finish_reason=FinishReason.STOP,
        ),
        ChatResponse(
            content=__import__("json").dumps(judge_payload),
            model=TARGET_MODEL,
            provider=TARGET_PROVIDER,
            usage=Usage(input_tokens=100, output_tokens=50),
            finish_reason=FinishReason.STOP,
        ),
    ]
    registry = MagicMock()
    registry.resolve.return_value = provider
    return registry, provider


async def _build_factory(*tables: Any) -> async_sessionmaker[Any]:
    """Create an in-memory SQLite database with the given tables."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, list(tables) or None)
    return async_sessionmaker(engine, expire_on_commit=False)


async def _create_running_run(factory: async_sessionmaker[Any]) -> AttackRun:
    """Create a run in RUNNING state (same as the real start path)."""
    async with factory() as session:
        repo = SqlAlchemyAttackRunRepository(session)
        run = AttackRun.create()
        run.queue()
        run.start(total_items=1)
        await repo.save(run)
        await session.commit()
        return run


FAKE_METRIC_RESULTS: dict[str, Any] = {
    "safety": {
        "score": 0.8,
        "normalized_score": 0.8,
        "raw_output": "safety check passed",
        "reasoning": "no harmful content detected",
        "confidence": 0.9,
        "version": "1.0.0",
    },
    "prompt_injection": {
        "score": 0.6,
        "normalized_score": 0.6,
        "raw_output": "injection attempt detected",
        "reasoning": "model partially resisted",
        "confidence": 0.85,
        "version": "1.0.0",
    },
    "jailbreak": {
        "score": 0.9,
        "normalized_score": 0.9,
        "raw_output": "jailbreak successful",
        "reasoning": "model was tricked",
        "confidence": 0.95,
        "version": "1.0.0",
    },
    "toxicity": {
        "score": 0.3,
        "normalized_score": 0.3,
        "raw_output": "low toxicity",
        "reasoning": "response was clean",
        "confidence": 0.8,
        "version": "1.0.0",
    },
    "bias": {
        "score": 0.2,
        "normalized_score": 0.2,
        "raw_output": "no bias detected",
        "reasoning": "response was neutral",
        "confidence": 0.75,
        "version": "1.0.0",
    },
}


class _FakeMetric(Metric):
    """Minimal deterministic metric returning a fixed MetricResult."""

    def __init__(self, name: str, result: Any) -> None:
        self._name = name
        self._result = result
        self._definition = MetricDefinition(
            name=name,
            display_name=name.replace("_", " ").title(),
            description=f"Fake {name} metric for testing",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            evaluator_type=EvaluatorType.LLM_JUDGE,
        )

    def definition(self) -> MetricDefinition:
        return self._definition

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        return MetricResult(
            metric_name=self._name,
            **dict(self._result.items()),
        )


def _safety_metric_engine() -> Any:
    from app.evaluation.metrics.engine import MetricEngine
    from app.evaluation.metrics.implementations.semantic_effectiveness_metric import (
        SemanticEffectivenessMetric,
    )

    engine = MetricEngine()
    engine.register(SemanticEffectivenessMetric())
    for name, result in FAKE_METRIC_RESULTS.items():
        engine.register(_FakeMetric(name, result))
    return engine


class TestMetricPersistenceFailurePropagates:
    """F7: persistence failure surfaces as a retryable error, not FAILED."""

    async def test_activity_raises_metric_persistence_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        factory = await _build_factory(
            AttackRunModel.__table__, MetricResultModel.__table__, RedTeamRoundModel.__table__
        )
        run = await _create_running_run(factory)
        registry, _provider = _fake_registry_provider(
            "I have the secret: sk-123",
            _fake_judge_payload(),
        )

        async def _boom(self: object, results: object) -> None:
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            SqlAlchemyMetricResultRepository,
            "save_many",
            _boom,
        )

        snapshot = (
            redteam_activities._provider_registry,
            redteam_activities._metric_engine,
            redteam_activities._session_factory,
        )
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_safety_metric_engine())
            configure_redteam_session_factory(factory)

            with pytest.raises(_MetricPersistenceError):
                await red_team_campaign_activity(
                    RedTeamWorkflowInput(
                        attack_run_id=str(run.id),
                        target_provider=TARGET_PROVIDER,
                        target_model=TARGET_MODEL,
                        max_rounds=1,
                    )
                )
        finally:
            (
                redteam_activities._provider_registry,
                redteam_activities._metric_engine,
                redteam_activities._session_factory,
            ) = snapshot

    async def test_persistence_failure_does_not_swallow_into_failed_result(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        factory = await _build_factory(
            AttackRunModel.__table__, MetricResultModel.__table__, RedTeamRoundModel.__table__
        )
        run = await _create_running_run(factory)
        registry, _provider = _fake_registry_provider(
            "I have the secret: sk-123",
            _fake_judge_payload(),
        )

        async def _boom(self: object, results: object) -> None:
            raise RuntimeError("disk full")

        monkeypatch.setattr(
            SqlAlchemyMetricResultRepository,
            "save_many",
            _boom,
        )

        snapshot = (
            redteam_activities._provider_registry,
            redteam_activities._metric_engine,
            redteam_activities._session_factory,
        )
        caught: Exception | None = None
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_safety_metric_engine())
            configure_redteam_session_factory(factory)

            try:
                await red_team_campaign_activity(
                    RedTeamWorkflowInput(
                        attack_run_id=str(run.id),
                        target_provider=TARGET_PROVIDER,
                        target_model=TARGET_MODEL,
                        max_rounds=1,
                    )
                )
            except _MetricPersistenceError as exc:
                caught = exc
        finally:
            (
                redteam_activities._provider_registry,
                redteam_activities._metric_engine,
                redteam_activities._session_factory,
            ) = snapshot

        # The error was NOT converted into a FAILED result â€” it surfaced
        # so Temporal's activity retry policy can re-run the attempt.
        assert caught is not None
        assert "disk full" in str(caught)

        async with factory() as session:
            repo = SqlAlchemyAttackRunRepository(session)
            persisted = await repo.find_by_id(run.id)
        assert persisted is not None
        assert persisted.status == AttackStatus.RUNNING


class TestMetricPersistenceRetry:
    """F7: a Temporal retry re-persists the result without re-invoking."""

    async def test_retry_persists_metrics_without_provider_reinvoke(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        factory = await _build_factory(
            AttackRunModel.__table__, MetricResultModel.__table__, RedTeamRoundModel.__table__
        )
        run = await _create_running_run(factory)
        registry, provider = _fake_registry_provider(
            "I have the secret: sk-123",
            _fake_judge_payload(),
        )

        real_save_many = SqlAlchemyMetricResultRepository.save_many
        failed = False

        async def _fail_once(self: object, results: object) -> None:
            nonlocal failed
            if not failed:
                failed = True
                raise RuntimeError("transient disk full")

        monkeypatch.setattr(
            SqlAlchemyMetricResultRepository,
            "save_many",
            _fail_once,
        )

        snapshot = (
            redteam_activities._provider_registry,
            redteam_activities._metric_engine,
            redteam_activities._session_factory,
        )
        try:
            configure_redteam_provider_registry(registry)
            configure_redteam_metric_engine(_safety_metric_engine())
            configure_redteam_session_factory(factory)

            # Attempt 1: metric persistence fails -> retryable error.
            with pytest.raises(_MetricPersistenceError):
                await red_team_campaign_activity(
                    RedTeamWorkflowInput(
                        attack_run_id=str(run.id),
                        target_provider=TARGET_PROVIDER,
                        target_model=TARGET_MODEL,
                        max_rounds=1,
                    )
                )

            # The retry boundary never re-invoked providers after the
            # first round was checkpointed durably.
            first_attempt_calls = _count_provider_calls(provider)

            # Attempt 2 (Temporal retry): persistence succeeds, replaying
            # the durably-completed round without provider re-invocation.
            monkeypatch.setattr(
                SqlAlchemyMetricResultRepository,
                "save_many",
                real_save_many,
            )
            outcome = await red_team_campaign_activity(
                RedTeamWorkflowInput(
                    attack_run_id=str(run.id),
                    target_provider=TARGET_PROVIDER,
                    target_model=TARGET_MODEL,
                    max_rounds=1,
                )
            )
        finally:
            (
                redteam_activities._provider_registry,
                redteam_activities._metric_engine,
                redteam_activities._session_factory,
            ) = snapshot

        assert outcome.total_rounds == 1

        # The retry did NOT re-run the provider for the completed round:
        # call count is unchanged between the two attempts.
        assert _count_provider_calls(provider) == first_attempt_calls

        async with factory() as session:
            metric_repo = SqlAlchemyMetricResultRepository(session)
            results = await metric_repo.find_by_run_id(run.id)
            run_repo = SqlAlchemyAttackRunRepository(session)
            persisted = await run_repo.find_by_id(run.id)

        # 1 semantic + 5 individual = 6 rows (the durable provider result).
        assert len(results) == 6
        metric_names = {r.metric_name for r in results}
        assert metric_names == {
            "semantic_effectiveness",
            "safety",
            "prompt_injection",
            "jailbreak",
            "toxicity",
            "bias",
        }
        assert persisted is not None
        assert persisted.status == AttackStatus.COMPLETED


def _count_provider_calls(provider: AsyncMock) -> int:
    """Return the number of provider.chat invocations (target + judge)."""
    return int(provider.chat.await_count)
