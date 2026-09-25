"""Regression tests: run collection/create tenant isolation (S-05).

Forensic audit found the two S-04 residuals are genuine defects — both
``POST /runs`` and ``GET /runs`` relied on ``get_current_user`` only:

* ``GET /runs`` lists every organization's runs (ids, parent evaluation
  ids, provider/model/status/cost metadata, exact totals) with fully
  caller-controlled filters and no tenant constraint anywhere down to
  ``SqlAlchemyEvaluationRunRepository.list``. A foreign ``evaluation_id``
  filter yields targeted cross-tenant listing.
* ``POST /runs`` persists ``body.evaluation_id`` (never existence- or
  ownership-checked — garbage ids yield 201) and ``body.project_id``
  (persisted to ``metadata.project_id``, the field S-04's orphan fallback
  trusts) and schedules the Temporal/provider execution BEFORE any
  ownership concept: cross-tenant evaluation planting, attribution
  spoofing, and server-credential provider spend. Idempotency replay
  returns unowned runs by key.

The fix reuses the shared boundaries only:
  - ``require_current_org_membership`` on both routes (create forces
    ``project_id`` from the JWT org, mirroring S-03's create_evaluation).
  - body ``evaluation_id``, when supplied, is ownership-checked via
    ``require_owned_evaluation`` BEFORE persistence and BEFORE any
    Temporal side effect (malformed/nonexistent -> truthful 404).
  - idempotency replay gates the returned run via ``require_owned_run``.
  - ``GET /runs`` scopes to owned evaluations + own orphans through a
    new ``RunQuery.owner_project_id`` predicate (JOIN, no new model).

These tests run the real chain with a stub session. The stub emulates
scoped vs unscoped SQL: unscoped list SQL returns every row (proving the
leak pre-fix); SQL carrying the tenant JOIN returns only in-scope rows.
``TestRunListTenantPredicate`` additionally executes the real repository
``list()`` against in-memory SQLite to prove the predicate semantics.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from hashlib import sha256
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.evaluation.domain.contracts.evaluation_contracts import RunQuery
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.tenant import MembershipModel
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)

ORG = "org-acme"
OTHER_ORG = "org-rival"
EVAL_OWNED = "00000000-0000-0000-0000-0000000000c1"
EVAL_VICTIM = "00000000-0000-0000-0000-0000000000c2"
EVAL_MISSING = "00000000-0000-0000-0000-0000000000cf"
RUN_O1 = "00000000-0000-0000-0000-0000000000d1"
RUN_O2_ORPHAN = "00000000-0000-0000-0000-0000000000d2"
RUN_V1 = "00000000-0000-0000-0000-0000000000d3"
RUN_V2_ORPHAN = "00000000-0000-0000-0000-0000000000d4"
USER = CurrentUser(user_id="user-creator", org_id=ORG)

CREATE_BODY = {
    "evaluation_id": EVAL_OWNED,
    "evaluation_name": "new-run",
    "provider": "openai",
    "model": "gpt-4o",
    "metrics": ["accuracy"],
}


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


def _literal(sql: str, column: str) -> str | None:
    match = re.search(re.escape(column) + r" = '([^']+)'", sql)
    return match.group(1) if match else None


class _StubSession:
    """Routes SQL to stub rows; emulates scoped vs unscoped run listing."""

    def __init__(self, *, membership=None, evaluations=None, runs=None):
        self._membership = membership
        self._evaluations = evaluations or {}
        self._runs = runs or {}
        self._saved: dict[str, object] = {}
        self.merged: list[object] = []

    @staticmethod
    def _which(sql: str, mapping: dict):
        for key, row in mapping.items():
            if key.lower() in sql:
                return row
        return None

    def _in_scope(self, row: EvaluationRunModel) -> bool:
        if row.evaluation_id:
            evaluation = self._evaluations.get(row.evaluation_id)
            return evaluation is not None and evaluation.project_id == ORG
        return (row.metadata_ or {}).get("project_id") == ORG

    def _scoped_rows(self, sql: str) -> list:
        rows = [r for r in self._runs.values() if self._in_scope(r)]
        evaluation_id = _literal(sql, "evaluation_runs.evaluation_id")
        if evaluation_id is not None:
            rows = [r for r in rows if (r.evaluation_id or "") == evaluation_id]
        status = _literal(sql, "evaluation_runs.status")
        if status is not None:
            rows = [r for r in rows if r.status == status]
        limit = re.search(r"limit (\d+)", sql)
        offset = re.search(r"offset (\d+)", sql)
        if limit is not None:
            start = int(offset.group(1)) if offset else 0
            rows = rows[start : start + int(limit.group(1))]
        return rows

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        if "memberships" in sql:
            return _StubResult(self._membership)
        if "evaluations" in sql and "evaluation_runs" not in sql:
            if "count(" in sql:
                return _StubResult(None, count=len(self._evaluations))
            return _StubResult(self._which(sql, self._evaluations))
        if "evaluation_runs" in sql:
            workflow_id = _literal(sql, "evaluation_runs.workflow_id")
            if workflow_id is not None:
                for row in self._runs.values():
                    if (row.workflow_id or "") == workflow_id:
                        return _StubResult(row)
                return _StubResult(None)
            if "count(" in sql:
                if "join" in sql:
                    return _StubResult(None, count=len(self._scoped_rows(sql)))
                return _StubResult(None, count=len(self._runs))
            if "limit" in sql:
                if "join" in sql:
                    return _StubResult(self._scoped_rows(sql))
                return _StubResult(list(self._runs.values()))
            row = self._which(sql, self._runs)
            if row is None:
                row = self._which(sql, self._saved)
            return _StubResult(row)
        return _StubResult(None)

    def add(self, _model):
        pass

    async def merge(self, model):
        self._saved[str(getattr(model, "id", ""))] = model
        self.merged.append(model)

    async def delete(self, _model):
        pass

    async def flush(self):
        pass


def _membership_row() -> MembershipModel:
    return MembershipModel(
        id="00000000-0000-0000-0000-0000000000aa",
        user_id=USER.user_id,
        organization_id=ORG,
        role="member",
        invited_by="user-owner",
        is_active=True,
        joined_at=datetime.now(UTC),
    )


def _evaluation_row(eval_id: str, *, project_id: str) -> EvaluationModel:
    now = datetime.now(UTC)
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
        created_at=now,
        updated_at=now,
    )


def _run_row(
    run_id: str,
    *,
    evaluation_id: str | None,
    project_id: str | None = None,
    status: str = "running",
    workflow_id: str | None = None,
) -> EvaluationRunModel:
    now = datetime.now(UTC)
    return EvaluationRunModel(
        id=run_id,
        evaluation_id=evaluation_id,
        evaluation_name="eval",
        workflow_id=workflow_id,
        provider="openai",
        model="gpt-4o",
        status=status,
        priority="normal",
        items_total=0,
        items_completed=0,
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
        started_at=now,
        completed_at=None,
        cancelled_at=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _idem(key: str) -> str:
    return f"evaluation-run-idem-{sha256(key.encode()).hexdigest()[:16]}"


def _mixed_world() -> tuple[dict, dict]:
    evaluations = {
        EVAL_OWNED: _evaluation_row(EVAL_OWNED, project_id=ORG),
        EVAL_VICTIM: _evaluation_row(EVAL_VICTIM, project_id=OTHER_ORG),
    }
    runs = {
        RUN_O1: _run_row(
            RUN_O1,
            evaluation_id=EVAL_OWNED,
            status="running",
            workflow_id=_idem("key-owned"),
        ),
        RUN_O2_ORPHAN: _run_row(
            RUN_O2_ORPHAN, evaluation_id=None, project_id=ORG, status="completed"
        ),
        RUN_V1: _run_row(
            RUN_V1,
            evaluation_id=EVAL_VICTIM,
            status="failed",
            workflow_id=_idem("key-victim"),
        ),
        RUN_V2_ORPHAN: _run_row(
            RUN_V2_ORPHAN, evaluation_id=None, project_id=OTHER_ORG, status="completed"
        ),
    }
    return evaluations, runs


def _victim_only_world() -> tuple[dict, dict]:
    evaluations = {EVAL_VICTIM: _evaluation_row(EVAL_VICTIM, project_id=OTHER_ORG)}
    runs = {
        RUN_V1: _run_row(RUN_V1, evaluation_id=EVAL_VICTIM, status="failed"),
        RUN_V2_ORPHAN: _run_row(
            RUN_V2_ORPHAN, evaluation_id=None, project_id=OTHER_ORG, status="completed"
        ),
    }
    return evaluations, runs


def _override_db(app, *, membership=None, evaluations=None, runs=None) -> _StubSession:
    session = _StubSession(membership=membership, evaluations=evaluations, runs=runs)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db_session] = lambda: session
    return session


@pytest.fixture
def temporal_mock():
    handle = MagicMock()
    handle.signal = AsyncMock()
    client = MagicMock()
    client.get_workflow_handle = MagicMock(return_value=handle)
    client.start_workflow = AsyncMock()
    return client


def _override_temporal(app, temporal_mock):
    app.dependency_overrides[get_temporal_client] = lambda: temporal_mock


# ---------------------------------------------------------------------------
# GET /runs
# ---------------------------------------------------------------------------


def test_list_runs_unauthenticated_rejected(client):
    assert client.get("/api/v1/runs").status_code == 401


def test_list_runs_non_member_forbidden(app, client):
    evaluations, runs = _mixed_world()
    _override_db(app, membership=None, evaluations=evaluations, runs=runs)
    assert client.get("/api/v1/runs").status_code == 403


def test_list_runs_same_tenant_only(app, client):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    response = client.get("/api/v1/runs")
    assert response.status_code == 200
    payload = response.json()
    assert {item["id"] for item in payload["items"]} == {RUN_O1, RUN_O2_ORPHAN}
    assert payload["total"] == 2


def test_list_runs_victim_only_world_is_empty(app, client):
    evaluations, runs = _victim_only_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    response = client.get("/api/v1/runs")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_list_runs_foreign_evaluation_filter_is_empty(app, client):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    response = client.get("/api/v1/runs", params={"evaluation_id": EVAL_VICTIM})
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_list_runs_owned_evaluation_filter(app, client):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    response = client.get("/api/v1/runs", params={"evaluation_id": EVAL_OWNED})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [RUN_O1]


def test_list_runs_unknown_and_malformed_evaluation_filter(app, client):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    assert (
        client.get("/api/v1/runs", params={"evaluation_id": EVAL_MISSING}).json()[
            "items"
        ]
        == []
    )
    assert (
        client.get("/api/v1/runs", params={"evaluation_id": "not-a-uuid"}).json()[
            "items"
        ]
        == []
    )


def test_list_runs_status_filter_within_scope(app, client):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    response = client.get("/api/v1/runs", params={"status": "failed"})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_runs_pagination_never_bleeds(app, client):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    first = client.get("/api/v1/runs", params={"page": 1, "page_size": 1}).json()
    second = client.get("/api/v1/runs", params={"page": 2, "page_size": 1}).json()
    assert first["total"] == 2
    assert {first["items"][0]["id"], second["items"][0]["id"]} == {
        RUN_O1,
        RUN_O2_ORPHAN,
    }


# ---------------------------------------------------------------------------
# POST /runs
# ---------------------------------------------------------------------------


def test_create_run_unauthenticated_rejected(client):
    assert client.post("/api/v1/runs", json=CREATE_BODY).status_code == 401


def test_create_run_non_member_forbidden_no_side_effects(app, client, temporal_mock):
    evaluations, runs = _mixed_world()
    session = _override_db(
        app, membership=None, evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    assert client.post("/api/v1/runs", json=CREATE_BODY).status_code == 403
    temporal_mock.start_workflow.assert_not_called()
    assert session.merged == []


def test_create_run_same_tenant_evaluation(app, client, temporal_mock):
    evaluations, runs = _mixed_world()
    session = _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    response = client.post("/api/v1/runs", json=CREATE_BODY)
    assert response.status_code == 201
    assert response.json()["evaluation_id"] == EVAL_OWNED
    temporal_mock.start_workflow.assert_called_once()
    saved = session.merged[0]
    assert saved.metadata_["project_id"] == ORG
    assert saved.evaluation_id == EVAL_OWNED


def test_create_run_project_spoof_is_ignored(app, client, temporal_mock):
    evaluations, runs = _mixed_world()
    session = _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    body = {**CREATE_BODY, "project_id": OTHER_ORG, "created_by": "attacker"}
    assert client.post("/api/v1/runs", json=body).status_code == 201
    assert session.merged[0].metadata_["project_id"] == ORG


def test_create_run_cross_tenant_evaluation_denied_no_side_effects(
    app, client, temporal_mock
):
    evaluations, runs = _mixed_world()
    session = _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    body = {**CREATE_BODY, "evaluation_id": EVAL_VICTIM}
    assert client.post("/api/v1/runs", json=body).status_code == 403
    temporal_mock.start_workflow.assert_not_called()
    assert session.merged == []


def test_create_run_nonexistent_evaluation_truthful_no_side_effects(
    app, client, temporal_mock
):
    evaluations, runs = _mixed_world()
    session = _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    body = {**CREATE_BODY, "evaluation_id": EVAL_MISSING}
    assert client.post("/api/v1/runs", json=body).status_code == 404
    temporal_mock.start_workflow.assert_not_called()
    assert session.merged == []


def test_create_run_malformed_evaluation_id_truthful_no_side_effects(
    app, client, temporal_mock
):
    evaluations, runs = _mixed_world()
    session = _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    body = {**CREATE_BODY, "evaluation_id": "not-a-uuid"}
    assert client.post("/api/v1/runs", json=body).status_code == 404
    temporal_mock.start_workflow.assert_not_called()
    assert session.merged == []


def test_create_run_orphan_attributes_caller_org(app, client, temporal_mock):
    evaluations, runs = _mixed_world()
    session = _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    body = {k: v for k, v in CREATE_BODY.items() if k != "evaluation_id"}
    response = client.post("/api/v1/runs", json=body)
    assert response.status_code == 201
    assert response.json()["evaluation_id"] is None
    temporal_mock.start_workflow.assert_called_once()
    assert session.merged[0].metadata_["project_id"] == ORG


def test_create_run_idempotent_replay_of_own_run(app, client, temporal_mock):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    response = client.post(
        "/api/v1/runs", json=CREATE_BODY, headers={"Idempotency-Key": "key-owned"}
    )
    assert response.status_code == 201
    assert response.json()["id"] == RUN_O1
    temporal_mock.start_workflow.assert_not_called()


def test_create_run_idempotent_replay_of_foreign_run_denied(
    app, client, temporal_mock
):
    evaluations, runs = _mixed_world()
    _override_db(
        app, membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    _override_temporal(app, temporal_mock)
    response = client.post(
        "/api/v1/runs", json=CREATE_BODY, headers={"Idempotency-Key": "key-victim"}
    )
    assert response.status_code == 403
    temporal_mock.start_workflow.assert_not_called()


# ---------------------------------------------------------------------------
# Repository predicate executed against real SQLite
# ---------------------------------------------------------------------------


class TestRunListTenantPredicate:
    """The owner predicate is semantically correct when really executed."""

    @pytest.fixture
    async def sqlite_repo(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.infrastructure.database.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    EvaluationModel.__table__,
                    EvaluationRunModel.__table__,
                ],
            )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(_evaluation_row(EVAL_OWNED, project_id=ORG))
            session.add(_evaluation_row(EVAL_VICTIM, project_id=OTHER_ORG))
            session.add(_run_row(RUN_O1, evaluation_id=EVAL_OWNED, status="running"))
            session.add(
                _run_row(
                    RUN_O2_ORPHAN,
                    evaluation_id=None,
                    project_id=ORG,
                    status="completed",
                )
            )
            session.add(_run_row(RUN_V1, evaluation_id=EVAL_VICTIM, status="failed"))
            session.add(
                _run_row(
                    RUN_V2_ORPHAN,
                    evaluation_id=None,
                    project_id=OTHER_ORG,
                    status="completed",
                )
            )
            await session.commit()
            yield SqlAlchemyEvaluationRunRepository(session)
        await engine.dispose()

    async def test_scoped_list_returns_only_own_runs(self, sqlite_repo):
        result = await sqlite_repo.list(RunQuery(owner_project_id=ORG))
        assert {str(item.id) for item in result.items} == {
            RUN_O1,
            RUN_O2_ORPHAN,
        }
        assert result.total == 2

    async def test_unscoped_list_returns_everything(self, sqlite_repo):
        result = await sqlite_repo.list(RunQuery())
        assert result.total == 4

    async def test_scoped_list_with_foreign_evaluation_filter_is_empty(
        self, sqlite_repo
    ):
        result = await sqlite_repo.list(
            RunQuery(owner_project_id=ORG, evaluation_id=EVAL_VICTIM)
        )
        assert result.items == []
        assert result.total == 0

    async def test_scoped_list_with_owned_evaluation_filter(self, sqlite_repo):
        result = await sqlite_repo.list(
            RunQuery(owner_project_id=ORG, evaluation_id=EVAL_OWNED)
        )
        assert [str(item.id) for item in result.items] == [RUN_O1]
