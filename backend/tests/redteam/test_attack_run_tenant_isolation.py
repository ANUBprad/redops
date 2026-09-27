"""Regression tests: red-team AttackRun tenant isolation (S-08).

Forensic audit established the truthful ownership contract from current
persistence (no manufacturing):

* LINKED AttackRuns (``evaluation_run_id`` set) are ownable through the
  S-04 run chain. Pre-fix, all seven run routes relied on
  ``get_current_user`` only: cross-tenant read/mutate/cancel plus
  Temporal-scheduled target/mutation provider spend on foreign
  campaigns, and creation accepted foreign/nonexistent/garbage
  evaluation ids with provider side effects.
* UNLINKED AttackRuns carry zero attribution (legal per schema, used by
  the lifecycle integration tests). No per-tenant gate can distinguish
  creator from attacker, so by-id routes explicitly ALLOW them — locked
  here as documented residual, not oversight. The scoped LIST (S-06
  owner predicate) excludes them: enumeration fails closed while
  targeted UUID access preserves the tested orphan flow.
* Attack DEFINITIONS have no tenant column at all (``created_by`` was
  body-spoofable free text); per-tenant gating is unimplementable
  without a migration. Out of scope; create now derives ``created_by``
  from the authenticated user as attribution hygiene.

Fix: shared ``require_owned_attack_run`` (resolve -> linked delegates
to ``require_owned_run``; unlinked allows, documented) on all run
by-id routes with the gate ordered BEFORE Temporal resolution;
creation attests a supplied ``evaluation_run_id`` before persistence;
list passes the S-06 owner predicate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.tenant import MembershipModel
from app.redteam.domain.enums import AttackStatus

ORG = "org-acme"
OTHER_ORG = "org-rival"
EVAL_OWNED = "00000000-0000-0000-0000-0000000000c1"
EVAL_VICTIM = "00000000-0000-0000-0000-0000000000c2"
EVAL_RUN_OWNED = "00000000-0000-0000-0000-0000000000d1"
EVAL_RUN_VICTIM = "00000000-0000-0000-0000-0000000000d2"
ATK_CREATED = "00000000-0000-0000-0000-0000000000e1"
ATK_RUNNING = "00000000-0000-0000-0000-0000000000e2"
ATK_VICTIM_CREATED = "00000000-0000-0000-0000-0000000000e3"
ATK_VICTIM_RUNNING = "00000000-0000-0000-0000-0000000000e4"
ATK_ORPHAN = "00000000-0000-0000-0000-0000000000e5"
ATK_VICTIM_ORPHAN = "00000000-0000-0000-0000-0000000000e6"
USER = CurrentUser(user_id="user-attacker", org_id=ORG)
NOW = datetime.now(UTC)

BY_ID_ROUTES = [
    ("get", f"/api/v1/redteam/runs/{ATK_VICTIM_RUNNING}", None),
    ("post", f"/api/v1/redteam/runs/{ATK_VICTIM_CREATED}/start", {"total_items": 1}),
    ("post", f"/api/v1/redteam/runs/{ATK_VICTIM_RUNNING}/complete", None),
    ("post", f"/api/v1/redteam/runs/{ATK_VICTIM_RUNNING}/fail", {"error_message": "x"}),
    ("post", f"/api/v1/redteam/runs/{ATK_VICTIM_RUNNING}/cancel", None),
]


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
    def __init__(self, *, membership=None, attacks=None, evaluations=None, runs=None):
        self._membership = membership
        self._attacks = attacks or {}
        self._evaluations = evaluations or {}
        self._runs = runs or {}
        self.merged: list[object] = []

    @staticmethod
    def _which(sql: str, mapping: dict):
        for key, row in mapping.items():
            if key.lower() in sql:
                return row
        return None

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        if "memberships" in sql:
            return _StubResult(self._membership)
        if "attack_runs" in sql:
            if "count(" in sql:
                if "join" in sql:
                    return _StubResult(
                        None,
                        count=len(
                            [a for a in self._attacks.values() if self._attack_in_scope(a)]
                        ),
                    )
                return _StubResult(None, count=len(self._attacks))
            if "limit" in sql:
                if "join" in sql:
                    return _StubResult(
                        [a for a in self._attacks.values() if self._attack_in_scope(a)]
                    )
                return _StubResult(list(self._attacks.values()))
            return _StubResult(self._which(sql, self._attacks))
        if "evaluation_runs" in sql:
            return _StubResult(self._which(sql, self._runs))
        if "evaluations" in sql:
            return _StubResult(self._which(sql, self._evaluations))
        return _StubResult(None)

    def _attack_in_scope(self, attack: AttackRunModel) -> bool:
        if not attack.evaluation_run_id:
            return False
        run = self._runs.get(attack.evaluation_run_id)
        if run is None or not run.evaluation_id:
            return False
        evaluation = self._evaluations.get(run.evaluation_id)
        return evaluation is not None and evaluation.project_id == ORG

    def add(self, _model):
        pass

    async def merge(self, model):
        self.merged.append(model)

    async def delete(self, _model):
        pass

    async def flush(self):
        pass

    async def commit(self):
        pass


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


def _attack_row(
    attack_id: str, eval_run_id: str | None, *, status: str
) -> AttackRunModel:
    return AttackRunModel(
        id=attack_id,
        evaluation_run_id=eval_run_id,
        status=status,
        attack_definition_ids=[],
        configuration={},
        items_total=3,
        items_completed=0,
        items_passed=0,
        items_violated=0,
        items_failed=0,
        campaign_results={"note": f"campaign-{attack_id[-2:]}"},
        version=1,
        started_at=NOW,
        completed_at=None,
        created_at=NOW,
        updated_at=NOW,
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


def _run_row(run_id: str, *, evaluation_id: str | None) -> EvaluationRunModel:
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
        metadata_={"project_id": ORG},
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


def _world() -> tuple[dict, dict, dict]:
    attacks = {
        ATK_CREATED: _attack_row(
            ATK_CREATED, EVAL_RUN_OWNED, status=AttackStatus.CREATED.value
        ),
        ATK_RUNNING: _attack_row(
            ATK_RUNNING, EVAL_RUN_OWNED, status=AttackStatus.RUNNING.value
        ),
        ATK_VICTIM_CREATED: _attack_row(
            ATK_VICTIM_CREATED, EVAL_RUN_VICTIM, status=AttackStatus.CREATED.value
        ),
        ATK_VICTIM_RUNNING: _attack_row(
            ATK_VICTIM_RUNNING, EVAL_RUN_VICTIM, status=AttackStatus.RUNNING.value
        ),
        ATK_ORPHAN: _attack_row(
            ATK_ORPHAN, None, status=AttackStatus.RUNNING.value
        ),
        ATK_VICTIM_ORPHAN: _attack_row(
            ATK_VICTIM_ORPHAN, None, status=AttackStatus.RUNNING.value
        ),
    }
    evaluations = {
        EVAL_OWNED: _evaluation_row(EVAL_OWNED, project_id=ORG),
        EVAL_VICTIM: _evaluation_row(EVAL_VICTIM, project_id=OTHER_ORG),
    }
    runs = {
        EVAL_RUN_OWNED: _run_row(EVAL_RUN_OWNED, evaluation_id=EVAL_OWNED),
        EVAL_RUN_VICTIM: _run_row(EVAL_RUN_VICTIM, evaluation_id=EVAL_VICTIM),
    }
    return attacks, evaluations, runs


def _override_db(app, *, membership=None) -> _StubSession:
    attacks, evaluations, runs = _world()
    session = _StubSession(
        membership=membership, attacks=attacks, evaluations=evaluations, runs=runs
    )
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


def _request(client, method, path, body):
    if body is None:
        return getattr(client, method)(path)
    return getattr(client, method)(path, json=body)


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_unauthenticated_is_rejected(client, method, path, body):
    assert _request(client, method, path, body).status_code == 401


def test_unauthenticated_create_and_list_rejected(client):
    assert client.post("/api/v1/redteam/runs", json={}).status_code == 401
    assert client.get("/api/v1/redteam/runs").status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_cross_tenant_attack_run_is_forbidden(app, client, method, path, body):
    _override_db(app, membership=_membership_row())
    assert _request(client, method, path, body).status_code == 403


def test_cross_tenant_list_excludes_foreign(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/redteam/runs").json()
    ids = {item["id"] for item in payload["items"]}
    assert ids == {ATK_CREATED, ATK_RUNNING}
    assert payload["total"] == 2
    assert ATK_VICTIM_CREATED not in ids
    assert ATK_VICTIM_RUNNING not in ids
    assert ATK_VICTIM_ORPHAN not in ids


def test_non_member_is_forbidden(app, client):
    _override_db(app, membership=None)
    assert client.get(f"/api/v1/redteam/runs/{ATK_RUNNING}").status_code == 403
    assert client.get("/api/v1/redteam/runs").status_code == 403
    assert client.post("/api/v1/redteam/runs", json={}).status_code == 403


def test_cross_tenant_start_schedules_nothing(app, client, temporal_mock):
    _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    response = client.post(
        f"/api/v1/redteam/runs/{ATK_VICTIM_CREATED}/start", json={"total_items": 1}
    )
    assert response.status_code == 403
    temporal_mock.start_workflow.assert_not_called()


def test_cross_tenant_cancel_signals_nothing(app, client, temporal_mock):
    _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    handle = temporal_mock.get_workflow_handle.return_value
    response = client.post(f"/api/v1/redteam/runs/{ATK_VICTIM_RUNNING}/cancel")
    assert response.status_code == 403
    handle.signal.assert_not_called()


def test_same_tenant_lifecycle_succeeds(app, client, temporal_mock):
    _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    assert client.get(f"/api/v1/redteam/runs/{ATK_RUNNING}").status_code == 200
    assert (
        client.post(
            f"/api/v1/redteam/runs/{ATK_CREATED}/start", json={"total_items": 1}
        ).status_code
        == 200
    )
    temporal_mock.start_workflow.assert_called_once()
    assert (
        client.post(f"/api/v1/redteam/runs/{ATK_RUNNING}/complete").status_code == 200
    )
    assert (
        client.post(
            f"/api/v1/redteam/runs/{ATK_RUNNING}/fail", json={"error_message": "x"}
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/redteam/runs/{ATK_RUNNING}/cancel").status_code == 200


def test_create_run_foreign_evaluation_denied_no_persistence(app, client):
    session = _override_db(app, membership=_membership_row())
    response = client.post(
        "/api/v1/redteam/runs", json={"evaluation_run_id": EVAL_RUN_VICTIM}
    )
    assert response.status_code == 403
    assert session.merged == []


def test_create_run_nonexistent_and_malformed_evaluation_truthful(app, client):
    _override_db(app, membership=_membership_row())
    missing = "00000000-0000-0000-0000-0000000000df"
    assert (
        client.post(
            "/api/v1/redteam/runs", json={"evaluation_run_id": missing}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/redteam/runs", json={"evaluation_run_id": "not-a-uuid"}
        ).status_code
        == 404
    )


def test_create_run_linked_and_orphan_succeed(app, client):
    _override_db(app, membership=_membership_row())
    linked = client.post(
        "/api/v1/redteam/runs", json={"evaluation_run_id": EVAL_RUN_OWNED}
    )
    assert linked.status_code == 201
    assert linked.json()["evaluation_run_id"] == EVAL_RUN_OWNED
    orphan = client.post("/api/v1/redteam/runs", json={})
    assert orphan.status_code == 201
    assert orphan.json()["evaluation_run_id"] is None


def test_nonexistent_attack_run_is_truthful(app, client):
    _override_db(app, membership=_membership_row())
    missing = "00000000-0000-0000-0000-0000000000ef"
    assert client.get(f"/api/v1/redteam/runs/{missing}").status_code == 404
    assert client.get("/api/v1/redteam/runs/not-a-uuid").status_code == 404


def test_orphan_attack_run_targeted_access_preserved(app, client):
    """Unlinked runs carry no attribution: targeted access stays working.

    Locked as the documented residual (not a gap in the gate): the
    lifecycle integration tests depend on this flow, and no ownership
    signal exists to scope it per-tenant.
    """
    _override_db(app, membership=_membership_row())
    assert client.get(f"/api/v1/redteam/runs/{ATK_ORPHAN}").status_code == 200


def test_definition_create_derives_created_by(app, client):
    _override_db(app, membership=_membership_row())
    response = client.post(
        "/api/v1/redteam/definitions",
        json={
            "name": "prompt-injection",
            "category": "prompt_injection",
            "severity": "high",
            "prompt_template": "ignore {x}",
            "created_by": "spoofed-user",
        },
    )
    assert response.status_code == 201
    assert response.json()["created_by"] == USER.user_id
