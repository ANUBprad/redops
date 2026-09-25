"""P6-C11 tests: evaluation item_id contract.

Enforces the canonical item identifier across the full execution path
(API -> workflow -> activity -> durable item execution -> metrics):

  - arbitrary non-UUID strings are supported (not UUID-only);
  - an explicitly supplied id must be non-empty;
  - maximum length is 128 characters;
  - 129+ character ids are rejected BEFORE any provider work;
  - the exact supplied identifier survives unchanged end to end;
  - omitted (None) ids keep the legacy ordinal fallback.

Fixes F5: previously a 37-128 character id paid the provider and the LLM
judges and then failed at PostgreSQL metric persistence, and a 129+
character id re-paid the provider on every durable retry.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.evaluation_run import _item_to_payload
from app.core.config import AppConfig
from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.evaluation.application.run_commands import RetryEvaluationRunCommand
from app.evaluation.application.run_handlers import RetryEvaluationRunHandler
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
)
from app.evaluation.metrics.domain import (
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.temporal import activities as eval_activities
from app.evaluation.temporal.activities import (
    PersistMetricResultsInput,
    configure_cost_calculator,
    configure_metric_engine,
    configure_provider_registry,
    configure_session_factory,
)
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.item_execution import ItemExecutionModel
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.providers.cost.defaults import build_default_cost_calculator
from app.providers.models.enums import FinishReason
from app.providers.models.responses import ChatResponse, Usage
from app.providers.registry.registry import ProviderRegistry
from app.schemas.evaluation_run import CreateEvaluationRunRequest, DatasetItemRequest

LONG_128 = "eval-item-" + ("x" * 118)
TOO_LONG_129 = "eval-item-" + ("y" * 119)
UNIQUE_INDEX = "uq_metric_results_run_item_metric"
ITEM_ANSWER = '{"answer": "Paris"}'


# ---------------------------------------------------------------------------
# Schema validation — Part 1 / Part 2 and matrix 1-10
# ---------------------------------------------------------------------------


def _request_with_item_id(item_id: str | None) -> CreateEvaluationRunRequest:
    """Build a create-run request whose single item carries the given id."""
    dataset_item: dict[str, str | None] = {"prompt": "What is 2 + 2?"}
    if item_id is not None:
        dataset_item["id"] = item_id
    return CreateEvaluationRunRequest(
        evaluation_name="item-id-contract",
        provider="openai",
        model="gpt-4o",
        metrics=["accuracy"],
        dataset_items=[DatasetItemRequest(**dataset_item)],
    )


def test_uuid_identifier_accepted() -> None:
    item_id = "00000000-0000-0000-0000-000000000001"
    req = _request_with_item_id(item_id)
    assert req.dataset_items[0].id == item_id


def test_uuidv7_identifier_accepted() -> None:
    from app.kernel.entities.base import UUIDv7

    item_id = str(UUIDv7.generate())
    req = _request_with_item_id(item_id)
    assert req.dataset_items[0].id == item_id


def test_non_uuid_string_accepted() -> None:
    req = _request_with_item_id("item-pass")
    assert req.dataset_items[0].id == "item-pass"


def test_thirty_six_char_identifier_accepted() -> None:
    item_id = "a" * 36
    assert _request_with_item_id(item_id).dataset_items[0].id == item_id


def test_thirty_seven_char_identifier_accepted() -> None:
    item_id = "a" * 37
    assert _request_with_item_id(item_id).dataset_items[0].id == item_id


def test_128_char_identifier_accepted_and_preserved() -> None:
    req = _request_with_item_id(LONG_128)
    assert req.dataset_items[0].id == LONG_128


def test_129_char_identifier_rejected() -> None:
    with pytest.raises(ValidationError):
        _request_with_item_id(TOO_LONG_129)


def test_empty_string_identifier_rejected() -> None:
    with pytest.raises(ValidationError):
        _request_with_item_id("")


def test_whitespace_only_identifier_accepted_and_preserved() -> None:
    # The repository's schema convention is min_length-based (like prompt):
    # no whitespace-only rejection exists, and ids must not be normalized,
    # so a whitespace-only id is accepted and preserved byte-exact.
    item_id = "   "
    req = _request_with_item_id(item_id)
    assert req.dataset_items[0].id == item_id


def test_explicit_invalid_identifier_does_not_fall_back_to_ordinal() -> None:
    # An EXPLICITLY supplied invalid string (empty or too long) is rejected
    # at the API, so it can never silently become the ordinal fallback. The
    # fallback survives only for omitted (None) ids.
    for invalid in ("", TOO_LONG_129):
        with pytest.raises(ValidationError):
            _request_with_item_id(invalid)


def test_omitted_identifier_keeps_ordinal_fallback_semantics() -> None:
    # None is the legacy contract: the payload omits item_id and the
    # activity derives str(item_index). This backwards-compatible path is
    # preserved and is the ONLY way the fallback can activate.
    req = _request_with_item_id(None)
    assert req.dataset_items[0].id is None
    payload = _item_to_payload(req.dataset_items[0])
    assert "item_id" not in payload


def test_exact_identifier_survives_item_to_payload() -> None:
    payload = _item_to_payload(DatasetItemRequest(prompt="p", id=LONG_128))
    assert payload["item_id"] == LONG_128


# ---------------------------------------------------------------------------
# Provider-before-validation guarantee — Part 5 and matrix 16
# ---------------------------------------------------------------------------


class CapturingTemporalClient:
    """Captures every workflow submission; the provider only runs inside a
    started evaluation workflow, so zero submissions means zero provider
    invocations on the real production path."""

    def __init__(self) -> None:
        self.submissions: list[tuple[object, Any, str]] = []

    async def start_workflow(
        self,
        workflow: object,
        args: Any,
        *,
        id: str,
        task_queue: str,
        **kwargs: object,
    ) -> None:
        self.submissions.append((workflow, args, id))


class FakeRunRepository:
    """In-memory run repository that records every save it sees."""

    def __init__(self) -> None:
        self._run = None
        self.saves = 0

    async def save(self, run: object) -> None:
        self.saves += 1
        self._run = run

    async def find_by_id(self, run_id: object) -> object:
        return self._run

    async def find_by_workflow_id(self, workflow_id: str) -> object | None:
        return None


def _evaluation_app(
    temporal_client: CapturingTemporalClient,
    repo: FakeRunRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    """Build the production app with the run-creation deps overridden."""
    cfg = AppConfig(
        TEMPORAL_TASK_QUEUE="redops-c11-queue",
        OPENAI_API_KEY="sk-test",
        ANTHROPIC_API_KEY="sk-test-ant",
    )
    monkeypatch.setattr("app.core.dependencies.get_config", lambda: cfg)
    monkeypatch.setattr("app.api.evaluation_run._get_repository", lambda s: repo)

    from app.api.router import api_router

    app = FastAPI()
    app.include_router(api_router)
    session: MagicMock = MagicMock(spec=AsyncSession)
    session.merge = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id="u")
    app.dependency_overrides[get_temporal_client] = lambda: temporal_client
    return app


def _post_run(client: TestClient, item_id: str):
    return client.post(
        "/api/v1/runs",
        json={
            "evaluation_name": "item-id-contract",
            "provider": "openai",
            "model": "gpt-4o",
            "metrics": ["accuracy"],
            "dataset_items": [{"prompt": "hello", "id": item_id}],
        },
    )


def test_invalid_item_id_rejected_before_provider_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 129-char id is rejected with 422 and no workflow is started, so the
    provider (reachable only after workflow start) can never be invoked."""
    tc = CapturingTemporalClient()
    repo = FakeRunRepository()
    app = _evaluation_app(tc, repo, monkeypatch)

    with TestClient(app) as client:
        response = _post_run(client, TOO_LONG_129)

    assert response.status_code == 422, response.text
    assert tc.submissions == [], "workflow must not start for an invalid id"
    assert repo.saves == 0, "no run may be persisted for an invalid id"


def test_128_char_identifier_reaches_workflow_input_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The accepted ceiling id flows through the real API into the workflow
    input unchanged — the only gateway to provider execution."""
    tc = CapturingTemporalClient()
    repo = FakeRunRepository()
    app = _evaluation_app(tc, repo, monkeypatch)

    with TestClient(app) as client:
        response = _post_run(client, LONG_128)

    assert response.status_code == 201, response.text
    assert len(tc.submissions) == 1
    _, workflow_input, _ = tc.submissions[0]
    assert workflow_input.dataset_items == ({"item_id": LONG_128, "prompt": "hello"},)


# ---------------------------------------------------------------------------
# Persistence — Part 6 / Part 7 and matrix 11-15
# ---------------------------------------------------------------------------


async def _make_database(*tables: Any) -> async_sessionmaker[Any]:
    """Create an in-memory SQLite database holding the given tables."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, list(tables) or None)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_activity_configuration() -> None:
    """Restore activity module globals after each test."""
    old = (
        eval_activities._session_factory,
        eval_activities._provider_registry,
        eval_activities._metric_engine,
        eval_activities._cost_calculator,
    )
    yield
    (
        eval_activities._session_factory,
        eval_activities._provider_registry,
        eval_activities._metric_engine,
        eval_activities._cost_calculator,
    ) = old


class RecordingChatProvider:
    """Provider that records every chat invocation and replies deterministically."""

    provider_name = "recording"

    def __init__(self) -> None:
        self.calls = 0

    async def chat(
        self,
        messages: list[Any],
        model: str,
        options: Any = None,
    ) -> ChatResponse:
        self.calls += 1
        return ChatResponse(
            content=ITEM_ANSWER,
            model=model,
            provider=self.provider_name,
            usage=Usage(input_tokens=7, output_tokens=3, total_tokens=10),
            finish_reason=FinishReason.STOP,
        )


class CountingMetric(Metric):
    """Metric that records how many times it evaluated."""

    def __init__(self) -> None:
        self.calls = 0

    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            name="counting",
            display_name="Counting",
            description="Counts evaluations deterministically",
            category=MetricCategory.QUALITY,
            scale=MetricScale.BINARY,
            version="1.0.0",
        )

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        self.calls += 1
        return MetricResult(
            metric_name="counting",
            score=0.42,
            normalized_score=0.42,
            version="1.0.0",
        )


def _configure_pipeline(
    factory: async_sessionmaker[Any],
    registry: ProviderRegistry,
    metric_engine: MetricEngine,
) -> None:
    """Wire the real activity dependencies, mirroring worker startup."""
    configure_session_factory(factory)
    configure_provider_registry(registry)
    configure_metric_engine(metric_engine)
    configure_cost_calculator(build_default_cost_calculator())


async def _durable_item_ids(
    factory: async_sessionmaker[Any],
    run_id: str,
) -> set[str]:
    async with factory() as session:
        rows = await session.scalars(
            select(ItemExecutionModel.item_id).where(ItemExecutionModel.run_id == run_id)
        )
        return set(rows)


async def _metric_rows(
    factory: async_sessionmaker[Any],
    run_id: str,
) -> list[MetricResultModel]:
    async with factory() as session:
        rows = await session.scalars(
            select(MetricResultModel).where(MetricResultModel.run_id == run_id)
        )
        return list(rows)


@pytest.mark.asyncio
async def test_128_char_item_id_flows_through_durable_and_metric_persistence() -> None:
    """Full chain with a 128-char arbitrary id: provider once, durable record
    exact, metric payload stamped, metric row persisted, C9 identity intact."""
    factory = await _make_database(
        ItemExecutionModel.__table__,
        MetricResultModel.__table__,
    )
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    metric = CountingMetric()
    engine = MetricEngine()
    engine.register(metric)
    _configure_pipeline(factory, registry, engine)

    result = await eval_activities.execute_item_activity(
        eval_activities.ExecuteItemInput(
            run_id="run-c11",
            item_index=0,
            provider_name="recording",
            model_id="gpt-4o",
            metric_names=("counting",),
            prompt="What is 2 + 2?",
            item_id=LONG_128,
        )
    )

    assert result.failed is False
    assert provider.calls == 1
    assert result.item_id == LONG_128
    assert len(result.metrics) == 1
    assert result.metrics[0].metadata["item_id"] == LONG_128

    durable_ids = await _durable_item_ids(factory, "run-c11")
    assert durable_ids == {LONG_128}

    snapshot = eval_activities._session_factory
    try:
        configure_session_factory(factory)
        for _ in range(2):
            await eval_activities.persist_metric_results_activity(
                PersistMetricResultsInput(
                    run_id="run-c11",
                    item_id=LONG_128,
                    results=result.metrics,
                )
            )
    finally:
        eval_activities._session_factory = snapshot

    rows = await _metric_rows(factory, "run-c11")
    assert len(rows) == 1, "C9 uniqueness: one row per (run_id, item_id, metric_name)"
    assert rows[0].item_id == LONG_128


@pytest.mark.asyncio
async def test_non_uuid_metric_upsert_with_128_char_id() -> None:
    """Non-UUID ids keep working through the C9 upsert path at the ceiling."""
    factory = await _make_database(MetricResultModel.__table__)
    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        await repo.save_many(
            [
                MetricResult(
                    metric_name="groundedness",
                    score=0.4,
                    normalized_score=0.4,
                    metadata={"run_id": "run-nonuuid", "item_id": LONG_128},
                )
            ]
        )
        await repo.save_many(
            [
                MetricResult(
                    metric_name="groundedness",
                    score=0.8,
                    normalized_score=0.8,
                    metadata={"run_id": "run-nonuuid", "item_id": LONG_128},
                )
            ]
        )
        await session.commit()

    rows = await _metric_rows(factory, "run-nonuuid")
    assert len(rows) == 1
    assert rows[0].item_id == LONG_128
    assert rows[0].score == 0.8


@pytest.mark.asyncio
async def test_128_char_item_id_survives_durable_retry() -> None:
    """Re-executing the same (run_id, 128-char id) reuses the durable record
    and never re-invokes the provider."""
    factory = await _make_database(ItemExecutionModel.__table__)
    provider = RecordingChatProvider()
    registry = ProviderRegistry()
    registry.register(provider)
    metric = CountingMetric()
    engine = MetricEngine()
    engine.register(metric)
    _configure_pipeline(factory, registry, engine)
    input_ = eval_activities.ExecuteItemInput(
        run_id="run-retry",
        item_index=0,
        provider_name="recording",
        model_id="gpt-4o",
        metric_names=("counting",),
        prompt="What is 2 + 2?",
        item_id=LONG_128,
    )

    first = await eval_activities.execute_item_activity(input_)
    second = await eval_activities.execute_item_activity(input_)

    assert first.failed is False and second.failed is False
    assert provider.calls == 1
    assert second.item_id == first.item_id == LONG_128
    assert await _durable_item_ids(factory, "run-retry") == {LONG_128}


@pytest.mark.asyncio
async def test_retry_handler_preserves_128_char_item_id_verbatim() -> None:
    """Retry/replay rehydrates the persisted config, so the exact 128-char id
    survives the retry path untouched."""
    config = EvaluationConfiguration(
        name="retry-source",
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        metrics=("accuracy",),
        dataset_items=({"item_id": LONG_128, "prompt": "p"},),
    )
    source = EvaluationRun(
        evaluation_name="retry-source",
        config=config,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
    )
    source.queue()
    source.start(total_items=1)
    source.fail(error_code="ERR", error_message="boom")
    source.collect_events()

    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=source)
    repo.save = AsyncMock()
    handler = RetryEvaluationRunHandler(repo)

    result = await handler.handle(RetryEvaluationRunCommand(run_id=str(source.id)))

    assert result.config.dataset_items == ({"item_id": LONG_128, "prompt": "p"},)


# ---------------------------------------------------------------------------
# Migration — Part 4 and matrix 18-19
# ---------------------------------------------------------------------------


def _load_migration_module() -> object:
    """Load migration 024 directly (alembic.versions is not a package)."""
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "024_widen_metric_results_item_id.py"
    )
    spec = importlib.util.spec_from_file_location(
        "024_widen_metric_results_item_id",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _load_migration_module()

_PRE_024_STATEMENTS = [
    text(
        "CREATE TABLE metric_results ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " run_id VARCHAR(36) NOT NULL,"
        " item_id VARCHAR(36) NOT NULL,"
        " metric_name VARCHAR(100) NOT NULL,"
        " metric_definition_id INTEGER,"
        " score FLOAT,"
        " normalized_score FLOAT,"
        " raw_output TEXT,"
        " reasoning TEXT,"
        " metadata JSON,"
        " execution_time_ms INTEGER,"
        " error TEXT,"
        " created_at DATETIME,"
        " confidence FLOAT,"
        " version VARCHAR(20),"
        " cost_usd FLOAT)"
    ),
    text(
        "CREATE UNIQUE INDEX uq_metric_results_run_item_metric"
        " ON metric_results (run_id, item_id, metric_name)"
    ),
    text("CREATE INDEX ix_metric_results_run_item ON metric_results (run_id, item_id)"),
    text("CREATE INDEX ix_metric_results_run_metric ON metric_results (run_id, metric_name)"),
]


def _seed_runs(conn: sa.engine.Connection) -> None:
    conn.execute(
        text(
            "INSERT INTO metric_results "
            "(run_id, item_id, metric_name, score) VALUES "
            "('run-1', 'item-1', 'safety', 0.4), "
            "('run-1', 'item-2', 'safety', 0.7), "
            "('run-2', :long, 'safety', 0.6)"
        ),
        {"long": "pre-widening-arbitrary-id-" + ("x" * 10)},
    )


def _pre_024_engine() -> sa.engine.Engine:
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for stmt in _PRE_024_STATEMENTS:
            conn.execute(stmt)
        _seed_runs(conn)
    return engine


def _run_upgrade(engine: sa.engine.Engine) -> None:
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _MIGRATION.upgrade()


def _run_downgrade(engine: sa.engine.Engine) -> None:
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _MIGRATION.downgrade()


def _item_id_length(inspector: object) -> int | None:
    for c in inspector.get_columns("metric_results"):
        if c["name"] == "item_id":
            return c["type"].length
    return None


def _has_unique_identity_index(inspector: object) -> bool:
    """SQLite reports unique constraints as constraints, Postgres as indexes."""
    names = {i["name"] for i in inspector.get_indexes("metric_results") if i.get("name")}
    constraints = {
        c["name"] for c in inspector.get_unique_constraints("metric_results") if c.get("name")
    }
    return UNIQUE_INDEX in names or UNIQUE_INDEX in constraints


def test_migration_024_upgrade_widens_item_id_on_sqlite() -> None:
    engine = _pre_024_engine()
    _run_upgrade(engine)
    try:
        with engine.connect() as conn:
            inspector = sa.inspect(conn)
            assert _item_id_length(inspector) == 128
            assert _has_unique_identity_index(inspector)

        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT run_id, item_id, metric_name FROM metric_results ORDER BY run_id")
            ).fetchall()
        assert len(rows) == 3
        assert rows[0] == ("run-1", "item-1", "safety")
        assert rows[1] == ("run-1", "item-2", "safety")
        assert rows[2][1].startswith("pre-widening-arbitrary-id-")

        # The C9 unique identity is still enforced after the table rebuild.
        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO metric_results "
                        "(run_id, item_id, metric_name, score) "
                        "VALUES ('run-1', 'item-1', 'safety', 0.5)"
                    )
                )
    finally:
        engine.dispose()


def test_migration_024_downgrade_restores_36() -> None:
    engine = _pre_024_engine()
    _run_upgrade(engine)
    _run_downgrade(engine)
    try:
        with engine.connect() as conn:
            assert _item_id_length(sa.inspect(conn)) == 36
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT count(*) FROM metric_results")).fetchone()
        assert rows == (3,)
    finally:
        engine.dispose()


def test_migration_024_reapply_is_noop() -> None:
    engine = _pre_024_engine()
    _run_upgrade(engine)
    _run_upgrade(engine)
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT count(*) FROM metric_results")).fetchone()
        assert rows == (3,)
    finally:
        engine.dispose()
