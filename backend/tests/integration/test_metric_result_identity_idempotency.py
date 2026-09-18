"""P6-C9 tests: metric result identity and persistence idempotency.

Enforces one MetricResult row per (run_id, item_id, metric_name):

    A  saving the same metric twice persists one row (latest content)
    B  identity works for non-UUID items (not a UUID-gated rule)
    C  concurrent writes of the same result still yield one row
    D  multiple metrics on one item persist one row per metric
    E  different items persist one row per item
    F  a retry re-persists the already-produced result without re-invoking
    G  a persistence failure propagates (retryable), nothing is swallowed
    H  the user-facing /score handlers collapse duplicate requests
    I  the orchestration PersistenceStage is idempotent
    J  the database itself enforces the unique identity (not just the app)

Migration safety: applying 023 to a pre-C9 table adds the drifted columns,
collapses duplicate triples to the newest MAX(id) row, keeps the distinct
rows untouched, installs the unique index, and is a no-op on re-apply.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.evaluation.metrics.commands import ScoreBatchCommand, ScoreItemCommand
from app.evaluation.metrics.domain import (
    EvaluatorType,
    Metric,
    MetricCategory,
    MetricDefinition,
    MetricInput,
    MetricResult,
    MetricScale,
)
from app.evaluation.metrics.engine import MetricEngine
from app.evaluation.metrics.handlers import ScoreBatchHandler, ScoreItemHandler
from app.evaluation.orchestration.executor import PersistenceStage
from app.evaluation.temporal import activities as eval_activities
from app.evaluation.temporal.activities import (
    PersistMetricResultsInput,
    configure_session_factory,
    persist_metric_results_activity,
)
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.kernel.entities.base import UUIDv7

UNIQUE_INDEX = "uq_metric_results_run_item_metric"


def _load_migration_module() -> object:
    """Load migration 023 directly (alembic.versions is not a package)."""
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "023_metric_result_identity_uniqueness.py"
    )
    spec = importlib.util.spec_from_file_location("023_metric_result_identity_uniqueness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _load_migration_module()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _session_factory(*tables: object) -> async_sessionmaker[object]:
    """Return an in-memory SQLite factory holding the given tables."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, list(tables) or None)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    factory._engine = engine
    return factory


def _domain_result(
    metric_name: str,
    run_id: str,
    item_id: str,
    score: float = 0.5,
) -> MetricResult:
    return MetricResult(
        metric_name=metric_name,
        score=score,
        normalized_score=score,
        raw_output="raw-output",
        reasoning="reasoning",
        metadata={"run_id": run_id, "item_id": item_id},
        execution_time_ms=10,
        confidence=0.8,
        version="1.0.0",
        cost_usd=0.01,
    )


async def _rows(factory: async_sessionmaker[object]) -> list[MetricResultModel]:
    async with factory() as session:
        result = await session.execute(select(MetricResultModel).order_by(MetricResultModel.id))
        return list(result.scalars().all())


def _restore_session_factory(snapshot: object) -> None:
    eval_activities._session_factory = snapshot


# ---------------------------------------------------------------------------
# A / B — duplicates collapse to a single identity row
# ---------------------------------------------------------------------------


async def test_duplicate_save_collapses_to_single_row() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_id = str(UUIDv7.generate())

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        await repo.save_many([_domain_result("safety", run_id, item_id, score=0.5)])
        await repo.save_many([_domain_result("safety", run_id, item_id, score=0.9)])
        await session.commit()

    rows = await _rows(factory)
    assert len(rows) == 1
    assert rows[0].metric_name == "safety"
    assert rows[0].score == 0.9


async def test_non_uuid_identifiers_deduplicated() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = "run-without-uuid"
    item_id = "item-1"

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        await repo.save_many([_domain_result("groundedness", run_id, item_id, score=0.4)])
        await repo.save_many([_domain_result("groundedness", run_id, item_id, score=0.8)])
        await session.commit()

    rows = await _rows(factory)
    assert len(rows) == 1
    assert rows[0].run_id == run_id
    assert rows[0].item_id == item_id
    assert rows[0].score == 0.8


# ---------------------------------------------------------------------------
# C — concurrent writers of the same result still yield one row
# ---------------------------------------------------------------------------


async def test_concurrent_writes_yield_single_row(tmp_path: Path) -> None:
    path = str(tmp_path / "concurrent.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}", poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, [MetricResultModel.__table__])

        run_id = str(UUIDv7.generate())
        item_id = str(UUIDv7.generate())

        async def _persist(score: float) -> None:
            async with factory() as session:
                repo = SqlAlchemyMetricResultRepository(session)
                await repo.save_many([_domain_result("safety", run_id, item_id, score=score)])
                await session.commit()

        await asyncio.gather(_persist(0.5), _persist(0.9))

        rows = await _rows(factory)
        assert len(rows) == 1
        assert rows[0].score in (0.5, 0.9)
    finally:
        await engine.dispose()
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# D / E — identity granularity
# ---------------------------------------------------------------------------


async def test_multiple_metrics_one_row_per_metric() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_id = str(UUIDv7.generate())

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        await repo.save_many(
            [
                _domain_result("safety", run_id, item_id),
                _domain_result("groundedness", run_id, item_id),
                _domain_result("jailbreak", run_id, item_id),
            ]
        )
        await session.commit()

    rows = await _rows(factory)
    assert len(rows) == 3
    assert {r.metric_name for r in rows} == {"safety", "groundedness", "jailbreak"}
    assert len({r.metric_name for r in rows}) == len(rows)


async def test_different_items_one_row_per_item() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_a = str(UUIDv7.generate())
    item_b = str(UUIDv7.generate())

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        await repo.save_many(
            [
                _domain_result("safety", run_id, item_a),
                _domain_result("safety", run_id, item_b),
            ]
        )
        await session.commit()

    rows = await _rows(factory)
    assert len(rows) == 2
    assert {r.item_id for r in rows} == {item_a, item_b}


# ---------------------------------------------------------------------------
# F — retry re-persists identical results without re-invoking
# ---------------------------------------------------------------------------


class _CountingMetric(Metric):
    """Deterministic metric that counts its own evaluate calls."""

    def __init__(self, name: str, score: float = 0.6) -> None:
        self._name = name
        self._score = score
        self.calls = 0
        self._definition = MetricDefinition(
            name=name,
            display_name=name,
            description=f"fake {name} metric",
            category=MetricCategory.QUALITY,
            scale=MetricScale.CONTINUOUS,
            evaluator_type=EvaluatorType.LLM_JUDGE,
        )

    def definition(self) -> MetricDefinition:
        return self._definition

    async def evaluate(self, input_data: MetricInput) -> MetricResult:
        self.calls += 1
        return MetricResult(
            metric_name=self._name,
            score=self._score,
            normalized_score=self._score,
            raw_output="raw-output",
            reasoning="reasoning",
            confidence=0.8,
            version="1.0.0",
        )


async def test_activity_retry_reuses_result_without_reinvoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_id = "item-1"

    metric = _CountingMetric("safety", score=0.6)
    engine = MetricEngine()
    engine.register(metric)

    result = await engine.evaluate_single("safety", MetricInput(prompt="p", response="r"))
    payload = (
        eval_activities.MetricResultPayload(
            metric_name=result.metric_name,
            score=result.score,
            normalized_score=result.normalized_score,
            raw_output=result.raw_output,
            reasoning=result.reasoning,
            confidence=result.confidence,
            version=result.version,
            cost_usd=result.cost_usd,
            execution_time_ms=result.execution_time_ms,
        ),
    )

    snapshot = eval_activities._session_factory
    try:
        configure_session_factory(factory)
        await persist_metric_results_activity(
            PersistMetricResultsInput(run_id=run_id, item_id=item_id, results=payload)
        )
        await persist_metric_results_activity(
            PersistMetricResultsInput(run_id=run_id, item_id=item_id, results=payload)
        )
    finally:
        _restore_session_factory(snapshot)

    # The provider/metric was never re-invoked by the persistence retry.
    assert metric.calls == 1
    rows = await _rows(factory)
    assert len(rows) == 1
    assert rows[0].score == 0.6


# ---------------------------------------------------------------------------
# G — persistence failure propagates as a retryable error
# ---------------------------------------------------------------------------


async def test_persistence_failure_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_id = str(UUIDv7.generate())

    async def _boom(self: object, results: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(SqlAlchemyMetricResultRepository, "save_many", _boom)

    payload = (
        eval_activities.MetricResultPayload(
            metric_name="safety",
            score=0.6,
            normalized_score=0.6,
            confidence=0.8,
            version="1.0.0",
        ),
    )
    snapshot = eval_activities._session_factory
    try:
        configure_session_factory(factory)
        with pytest.raises(RuntimeError, match="disk full"):
            await persist_metric_results_activity(
                PersistMetricResultsInput(run_id=run_id, item_id=item_id, results=payload)
            )
    finally:
        _restore_session_factory(snapshot)


# ---------------------------------------------------------------------------
# H — the /score handler family collapses duplicate requests
# ---------------------------------------------------------------------------


async def test_score_handler_duplicate_requests_single_row() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_id = str(UUIDv7.generate())

    metric = _CountingMetric("safety", score=0.6)
    engine = MetricEngine()
    engine.register(metric)

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        handler = ScoreItemHandler(engine, repo)
        command = ScoreItemCommand(
            run_id=str(run_id),
            item_id=str(item_id),
            prompt="p",
            response="r",
            metric_names=("safety",),
        )
        await handler.handle(command)
        await session.commit()
        await handler.handle(command)
        await session.commit()

    # Each request legitimately re-evaluates, but only one row survives.
    assert metric.calls == 2
    rows = await _rows(factory)
    assert len(rows) == 1


async def test_score_batch_handler_duplicate_single_row_per_item() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_a = str(UUIDv7.generate())
    item_b = str(UUIDv7.generate())

    metric = _CountingMetric("safety", score=0.6)
    engine = MetricEngine()
    engine.register(metric)

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        handler = ScoreBatchHandler(ScoreItemHandler(engine, repo))
        command = ScoreBatchCommand(
            run_id=str(run_id),
            items=(
                ScoreItemCommand(
                    run_id=str(run_id),
                    item_id=str(item_a),
                    prompt="p",
                    response="r",
                    metric_names=("safety",),
                ),
                ScoreItemCommand(
                    run_id=str(run_id),
                    item_id=str(item_b),
                    prompt="p",
                    response="r",
                    metric_names=("safety",),
                ),
            ),
        )
        await handler.handle(command)
        await session.commit()
        await handler.handle(command)
        await session.commit()

    rows = await _rows(factory)
    assert len(rows) == 2
    assert {r.item_id for r in rows} == {item_a, item_b}


# ---------------------------------------------------------------------------
# I — the orchestration PersistenceStage is idempotent
# ---------------------------------------------------------------------------


async def test_orchestration_persistence_stage_idempotent() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    context = SimpleNamespace(run_id="run-1")
    shared_state = {
        "metric_results": {
            0: [
                MetricResult(
                    metric_name="safety",
                    score=0.5,
                    normalized_score=0.5,
                    raw_output="raw-output",
                    reasoning="reasoning",
                    metadata={"run_id": "ignored"},
                )
            ]
        }
    }

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        stage = PersistenceStage(metric_result_repository=repo)
        await stage.execute(context, steps=(), shared_state=shared_state)
        await session.commit()
        await stage.execute(context, steps=(), shared_state=shared_state)
        await session.commit()

    rows = await _rows(factory)
    assert len(rows) == 1
    assert rows[0].run_id == "run-1"
    assert rows[0].item_id == "0"
    assert rows[0].metric_name == "safety"


# ---------------------------------------------------------------------------
# J — the database enforces identity, not just the application
# ---------------------------------------------------------------------------


async def test_database_enforces_uniqueness() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    run_id = str(UUIDv7.generate())
    item_id = str(UUIDv7.generate())

    async with factory() as session:
        repo = SqlAlchemyMetricResultRepository(session)
        await repo.save_many([_domain_result("safety", run_id, item_id)])
        await session.commit()

        with pytest.raises(sa.exc.IntegrityError):
            await session.execute(
                text(
                    "INSERT INTO metric_results "
                    "(run_id, item_id, metric_name, score) "
                    "VALUES (:run, :item, :name, :score)"
                ),
                {"run": run_id, "item": item_id, "name": "safety", "score": 0.9},
            )
            await session.commit()

    rows = await _rows(factory)
    assert len(rows) == 1


def _has_unique_identity_index(inspector: object) -> bool:
    """SQLite reports unique constraints as constraints, Postgres as indexes."""
    names = {i["name"] for i in inspector.get_indexes("metric_results") if i.get("name")}
    constraints = {
        c["name"] for c in inspector.get_unique_constraints("metric_results") if c.get("name")
    }
    return UNIQUE_INDEX in names or UNIQUE_INDEX in constraints


async def test_unique_identity_index_present() -> None:
    factory = await _session_factory(MetricResultModel.__table__)
    async with factory._engine.begin() as conn:
        present = await conn.run_sync(
            lambda sync_conn: _has_unique_identity_index(sa.inspect(sync_conn))
        )
    assert present


# ---------------------------------------------------------------------------
# Migration safety — 023 reconciliation
# ---------------------------------------------------------------------------

_PRE_C9_DDL = text(
    """
    CREATE TABLE metric_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id VARCHAR(36) NOT NULL,
        item_id VARCHAR(36) NOT NULL,
        metric_name VARCHAR(100) NOT NULL,
        metric_definition_id INTEGER,
        score FLOAT,
        normalized_score FLOAT,
        raw_output TEXT,
        reasoning TEXT,
        metadata JSON,
        execution_time_ms INTEGER,
        error TEXT,
        created_at DATETIME
    );
    """
)


def _run_upgrade(engine: sa.engine.Engine) -> None:
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            _MIGRATION.upgrade()


def _pre_c9_engine() -> sa.engine.Engine:
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(_PRE_C9_DDL)
        conn.execute(
            text(
                "INSERT INTO metric_results "
                "(run_id, item_id, metric_name, score) VALUES "
                "('run-1', 'item-1', 'safety', 0.4), "
                "('run-1', 'item-1', 'safety', 0.9), "
                "('run-1', 'item-2', 'safety', 0.7)"
            )
        )
    return engine


async def test_migration_023_reconciles_and_dedups() -> None:
    engine = _pre_c9_engine()
    _run_upgrade(engine)
    try:
        with engine.connect() as conn:
            columns = {c["name"] for c in sa.inspect(conn).get_columns("metric_results")}
            assert {"confidence", "version", "cost_usd"} <= columns
            assert _has_unique_identity_index(sa.inspect(conn))

        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT run_id, item_id, metric_name, score, id FROM metric_results ORDER BY id"
                )
            ).fetchall()
        # Duplicate (run-1, item-1, safety) collapsed to the newest row; the
        # distinct (run-1, item-2, safety) row was left untouched.
        assert len(rows) == 2
        assert rows[0] == ("run-1", "item-1", "safety", 0.9, 2)
        assert rows[1] == ("run-1", "item-2", "safety", 0.7, 3)

        # The installed unique index now rejects a duplicate insert.
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


async def test_migration_023_reapply_is_noop() -> None:
    engine = _pre_c9_engine()
    _run_upgrade(engine)
    _run_upgrade(engine)
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT count(*) FROM metric_results")).fetchone()
        assert rows == (2,)
    finally:
        engine.dispose()
