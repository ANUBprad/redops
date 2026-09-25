"""Regression tests: score/score-batch attestation semantics (S-10).

Forensic verdict: DUAL_MODE with ownership-on-persisted.

* Ad-hoc scoring with arbitrary (wellformed, unpersisted) run/item ids
  is an established, tested contract (HEAD test_metrics_api scores
  random UUIDs expecting 200; no backend/frontend callers; the handler
  never loads a run). It must keep working.
* But score persists through the SAME canonical C9 upsert
  (run_id, item_id, metric_name) as orchestrated execution
  (executor + workflow persistence), overwriting score, reasoning,
  confidence, version, cost and metadata — with judge/embedding
  provider work happening first. Any authenticated caller can therefore
  overwrite another tenant's live metric rows under a known triple.
* Score returns only freshly computed results (no stored reads), so
  there is no confidentiality defect — this is integrity + billing.

Fix (narrow, Model C): before any engine/provider work or persistence,
if ``run_id`` resolves to a persisted EvaluationRun, require ownership
(require_owned_run); unpersisted ids stay ad-hoc; malformed ids are
truthfully 404 (previously 500). Batch attests every distinct run_id
and fails closed. Item existence is deliberately NOT attested: it adds
nothing cross-tenant once the run is owned, and could break unknown
legitimate flows.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
)
from app.evaluation.metrics.domain import MetricResult
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.models.tenant import MembershipModel
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)

ORG = "org-acme"
OTHER_ORG = "org-rival"
EVAL_OWNED = "00000000-0000-0000-0000-0000000000c1"
EVAL_VICTIM = "00000000-0000-0000-0000-0000000000c2"
RUN_OWNED = "00000000-0000-0000-0000-0000000000d1"
RUN_VICTIM = "00000000-0000-0000-0000-0000000000d2"
RUN_ORPHAN_OWN = "00000000-0000-0000-0000-0000000000d3"
RUN_ORPHAN_FOREIGN = "00000000-0000-0000-0000-0000000000d4"
RUN_ADHOC = "00000000-0000-0000-0000-0000000000d5"
ITEM_ADHOC = "00000000-0000-0000-0000-0000000000e5"
ITEM_A = "00000000-0000-0000-0000-0000000000e1"
USER = CurrentUser(user_id="user-scorer", org_id=ORG)
NOW = datetime.now(UTC)
LOCAL_METRICS = ["json_validity"]


class _StubScalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _StubResult:
    def __init__(self, value, *, count=0):
        self._single = value if not isinstance(value, list) else None
        self._multi = [] if value is None else (value if isinstance(value, list) else [value])
        self._count = count

    def scalar_one_or_none(self):
        return self._single

    def scalar_one(self):
        if self._single is None:
            return self._count
        return self._single

    def scalar(self):
        if self._single is None:
            return self._count
        return self._single

    def scalars(self):
        return _StubScalars(self._multi)


class _StubSession:
    """Routes SQL to stub rows; records statements for side-effect proof."""

    def __init__(self, *, membership=None, evaluations=None, runs=None):
        self._membership = membership
        self._evaluations = evaluations or {}
        self._runs = runs or {}
        self.statements: list[str] = []

    @staticmethod
    def _which(sql: str, mapping: dict):
        for key, row in mapping.items():
            if key.lower() in sql:
                return row
        return None

    async def execute(self, stmt, *args):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        self.statements.append(sql)
        if "memberships" in sql:
            return _StubResult(self._membership)
        if "evaluation_runs" in sql:
            return _StubResult(self._which(sql, self._runs))
        if "evaluations" in sql:
            return _StubResult(self._which(sql, self._evaluations))
        return _StubResult(None)

    def add(self, _model):
        pass

    async def merge(self, _model):
        pass

    async def flush(self):
        pass

    @property
    def wrote_rows(self) -> bool:
        return any("insert" in sql for sql in self.statements)


def _membership_row() -> MembershipModel:
    return MembershipModel(
        id="00000000-0000-0000-0000-0000000000aa",
        user_id=USER.user_id,
        organization_id=ORG,
        role="member",
        invited_by="user-owner",
        is_active=True,
        joined_at=NOW,
    )


def _evaluation_row(eval_id: str, *, project_id: str) -> EvaluationModel:
    return EvaluationModel(
        id=eval_id,
        project_id=project_id,
        dataset_id=None,
        name="eval",
        description="",
        provider="openai",
        model="gpt-4o",
        metrics=["accuracy"],
        tags=[],
        configuration={},
        status="ready",
        created_by="user-owner",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _run_row(run_id: str, *, evaluation_id: str | None, project_id: str | None) -> EvaluationRunModel:
    return EvaluationRunModel(
        id=run_id,
        evaluation_id=evaluation_id,
        evaluation_name="eval",
        workflow_id=None,
        provider="openai",
        model="gpt-4o",
        status="completed",
        priority="normal",
        items_total=1,
        items_completed=1,
        items_failed=0,
        token_input=0,
        token_output=0,
        cost=0.0,
        average_latency_ms=0,
        failure_reason=None,
        config={
            "name": "eval",
            "eval_type": "single",
            "profile": {"provider_name": "openai", "model_id": "gpt-4o"},
            "metrics": ["accuracy"],
            "budget": {},
            "limits": {},
            "policy": {},
            "priority": "normal",
            "dataset_items": [],
        },
        profile={"provider_name": "openai", "model_id": "gpt-4o"},
        metadata_={"project_id": project_id},
        verdict=None,
        trace_data=None,
        provenance=None,
        fingerprint=None,
        started_at=NOW,
        completed_at=NOW,
        cancelled_at=None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _world() -> tuple[dict, dict]:
    evaluations = {
        EVAL_OWNED: _evaluation_row(EVAL_OWNED, project_id=ORG),
        EVAL_VICTIM: _evaluation_row(EVAL_VICTIM, project_id=OTHER_ORG),
    }
    runs = {
        RUN_OWNED: _run_row(RUN_OWNED, evaluation_id=EVAL_OWNED, project_id=ORG),
        RUN_VICTIM: _run_row(RUN_VICTIM, evaluation_id=EVAL_VICTIM, project_id=OTHER_ORG),
        RUN_ORPHAN_OWN: _run_row(RUN_ORPHAN_OWN, evaluation_id=None, project_id=ORG),
        RUN_ORPHAN_FOREIGN: _run_row(
            RUN_ORPHAN_FOREIGN, evaluation_id=None, project_id=OTHER_ORG
        ),
    }
    return evaluations, runs


def _override_db(app, *, membership=None) -> _StubSession:
    evaluations, runs = _world()
    session = _StubSession(membership=membership, evaluations=evaluations, runs=runs)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db_session] = lambda: session
    return session


@pytest.fixture
def engine_spy(monkeypatch):
    """Count MetricEngine.evaluate_batch calls (the provider-work boundary)."""
    from app.api.metrics import get_metric_engine

    engine = get_metric_engine()
    calls: list[tuple] = []
    original = engine.evaluate_batch

    async def spy(metric_names, input_data):
        calls.append(tuple(metric_names))
        return await original(metric_names, input_data)

    monkeypatch.setattr(engine, "evaluate_batch", spy)
    return calls


def _score_body(run_id: str, item_id: str = ITEM_A) -> dict:
    return {
        "run_id": run_id,
        "item_id": item_id,
        "prompt": '{"a": 1}',
        "response": "x",
        "metric_names": LOCAL_METRICS,
    }


def test_unauthenticated_score_rejected(client):
    assert client.post("/api/v1/metrics/score", json=_score_body(RUN_ADHOC)).status_code == 401


def test_ad_hoc_score_succeeds_and_persists(app, client, engine_spy):
    session = _override_db(app, membership=_membership_row())
    response = client.post("/api/v1/metrics/score", json=_score_body(RUN_ADHOC, ITEM_ADHOC))
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert engine_spy != []
    assert session.wrote_rows


def test_ad_hoc_batch_succeeds(app, client, engine_spy):
    _override_db(app, membership=_membership_row())
    body = {"items": [_score_body(RUN_ADHOC, ITEM_ADHOC), _score_body(RUN_ADHOC, ITEM_A)]}
    assert client.post("/api/v1/metrics/score-batch", json=body).status_code == 200
    assert engine_spy != []


def test_owned_run_score_succeeds(app, client, engine_spy):
    session = _override_db(app, membership=_membership_row())
    response = client.post("/api/v1/metrics/score", json=_score_body(RUN_OWNED))
    assert response.status_code == 200
    assert engine_spy != []
    assert session.wrote_rows


def test_foreign_run_score_denied_no_engine_no_write(app, client, engine_spy):
    session = _override_db(app, membership=_membership_row())
    response = client.post("/api/v1/metrics/score", json=_score_body(RUN_VICTIM))
    assert response.status_code == 403
    assert engine_spy == []
    assert not session.wrote_rows


def test_foreign_run_batch_denied_atomically(app, client, engine_spy):
    session = _override_db(app, membership=_membership_row())
    body = {"items": [_score_body(RUN_OWNED), _score_body(RUN_VICTIM)]}
    response = client.post("/api/v1/metrics/score-batch", json=body)
    assert response.status_code == 403
    assert engine_spy == []
    assert not session.wrote_rows


def test_nonexistent_run_scores_ad_hoc(app, client, engine_spy):
    missing = "00000000-0000-0000-0000-0000000000df"
    _override_db(app, membership=_membership_row())
    assert client.post("/api/v1/metrics/score", json=_score_body(missing)).status_code == 200
    assert engine_spy != []


def test_malformed_run_id_is_truthful(app, client, engine_spy):
    session = _override_db(app, membership=_membership_row())
    response = client.post("/api/v1/metrics/score", json=_score_body("not-a-uuid"))
    assert response.status_code == 404
    assert engine_spy == []
    assert not session.wrote_rows


def test_orphan_run_attribution(app, client, engine_spy):
    _override_db(app, membership=_membership_row())
    assert (
        client.post("/api/v1/metrics/score", json=_score_body(RUN_ORPHAN_OWN)).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/metrics/score", json=_score_body(RUN_ORPHAN_FOREIGN)
        ).status_code
        == 403
    )
    assert engine_spy != []


def test_non_member_owned_run_denied(app, client, engine_spy):
    session = _override_db(app, membership=None)
    response = client.post("/api/v1/metrics/score", json=_score_body(RUN_OWNED))
    assert response.status_code == 403
    assert engine_spy == []
    assert not session.wrote_rows


class TestCanonicalIdentityOverwrite:
    """The C9 upsert primitive: same (run, item, metric) overwrites."""

    @pytest.fixture
    async def sqlite_repo(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.infrastructure.database.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all, tables=[MetricResultModel.__table__]
            )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                MetricResultModel(
                    run_id=RUN_VICTIM,
                    item_id=ITEM_A,
                    metric_name="accuracy",
                    score=0.1,
                    normalized_score=0.1,
                    created_at=NOW,
                )
            )
            await session.commit()
            yield SqlAlchemyMetricResultRepository(session)
        await engine.dispose()

    async def test_same_identity_overwrites_canonical_row(self, sqlite_repo):
        repo = sqlite_repo
        await repo.save_many(
            [
                MetricResult(
                    metric_name="accuracy",
                    score=0.9,
                    normalized_score=0.9,
                    raw_output="forged",
                    reasoning="forged",
                    metadata={"run_id": RUN_VICTIM, "item_id": ITEM_A},
                    execution_time_ms=1,
                    error=None,
                    confidence=1.0,
                    version="9.9.9",
                    cost_usd=0.0,
                )
            ]
        )
        from app.kernel.entities.base import UUIDv7

        rows = await repo.find_by_run_id(UUIDv7.from_string(RUN_VICTIM))
        assert len(rows) == 1
        assert rows[0].score == 0.9
        assert rows[0].version == "9.9.9"
