"""Regression tests: experiment tenant isolation (S-07).

Forensic audit found the experiment surface in the pre-S-03 state:
create/list derive the tenant from the JWT without any membership check,
and all seven by-id routes (get/patch/delete/activate/complete/archive/
baseline) perform no ownership check at all — any authenticated caller can
read, modify, transition, delete, or plant baselines on another
organization's experiments. ``set_baseline`` additionally accepts an
unattested cross-aggregate ``run_id`` (never existence- or
ownership-checked).

The fix mirrors S-03 with the experiment tenant key
(``Experiment.project_id``):
  - ``require_owned_experiment`` (new shared gate): membership
    revalidation + ``project_id == org``; unknown/malformed ids
    truthfully 404; cross-tenant 403.
  - create/list via ``require_current_org_membership`` (attribution was
    already server-derived; membership was missing).
  - ``set_baseline`` additionally requires the run via the S-04
    ``require_owned_run`` boundary before mutation.
  - analytics ``experiment-comparison`` gates its ``experiment_id`` the
    same way (S-06 follow-through; its run path stays dead).

Real dependency chain with a stub session; removing any gate fails the
cross-tenant assertions.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
)
from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.experiment import ExperimentModel
from app.infrastructure.database.models.tenant import MembershipModel

ORG = "org-acme"
OTHER_ORG = "org-rival"
EXP_DRAFT = "00000000-0000-0000-0000-0000000000e1"
EXP_ACTIVE = "00000000-0000-0000-0000-0000000000e2"
EXP_VICTIM = "00000000-0000-0000-0000-0000000000e3"
EVAL_OWNED = "00000000-0000-0000-0000-0000000000c1"
EVAL_VICTIM = "00000000-0000-0000-0000-0000000000c2"
RUN_OWNED = "00000000-0000-0000-0000-0000000000d1"
RUN_VICTIM = "00000000-0000-0000-0000-0000000000d2"
USER = CurrentUser(user_id="user-attacker", org_id=ORG)
NOW = datetime.now(UTC)

BY_ID_ROUTES = [
    ("get", f"/api/v1/experiments/{EXP_VICTIM}", None),
    ("patch", f"/api/v1/experiments/{EXP_VICTIM}", {"description": "tampered"}),
    ("delete", f"/api/v1/experiments/{EXP_VICTIM}", None),
    ("post", f"/api/v1/experiments/{EXP_VICTIM}/activate", None),
    ("post", f"/api/v1/experiments/{EXP_VICTIM}/complete", None),
    ("post", f"/api/v1/experiments/{EXP_VICTIM}/archive", None),
    ("post", f"/api/v1/experiments/{EXP_VICTIM}/baseline", {"run_id": RUN_VICTIM}),
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
    def __init__(self, *, membership=None, experiments=None, evaluations=None, runs=None):
        self._membership = membership
        self._experiments = experiments or {}
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
        if "experiments" in sql:
            project = re.search(r"experiments\.project_id = '([^']+)'", sql)
            name = re.search(r"experiments\.name = '([^']+)'", sql)
            rows = list(self._experiments.values())
            if project is not None:
                rows = [r for r in rows if r.project_id == project.group(1)]
            if name is not None:
                rows = [r for r in rows if r.name == name.group(1)]
            if "count(" in sql:
                return _StubResult(None, count=len(rows))
            if "limit" in sql or "exists" in sql:
                return _StubResult(rows)
            return _StubResult(self._which(sql, self._experiments))
        if "evaluation_runs" in sql:
            return _StubResult(self._which(sql, self._runs))
        if "evaluations" in sql:
            return _StubResult(self._which(sql, self._evaluations))
        return _StubResult(None)

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


def _experiment_row(exp_id: str, *, project_id: str, status: str) -> ExperimentModel:
    return ExperimentModel(
        id=exp_id,
        project_id=project_id,
        name="exp",
        description=None,
        hypothesis=None,
        status=status,
        baseline_run_id=None,
        conclusion=None,
        tags=[],
        created_by="user-owner",
        version=1,
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
    experiments = {
        EXP_DRAFT: _experiment_row(
            EXP_DRAFT, project_id=ORG, status=ExperimentStatus.DRAFT.value
        ),
        EXP_ACTIVE: _experiment_row(
            EXP_ACTIVE, project_id=ORG, status=ExperimentStatus.ACTIVE.value
        ),
        EXP_VICTIM: _experiment_row(
            EXP_VICTIM, project_id=OTHER_ORG, status=ExperimentStatus.DRAFT.value
        ),
    }
    evaluations = {
        EVAL_OWNED: _evaluation_row(EVAL_OWNED, project_id=ORG),
        EVAL_VICTIM: _evaluation_row(EVAL_VICTIM, project_id=OTHER_ORG),
    }
    runs = {
        RUN_OWNED: _run_row(RUN_OWNED, evaluation_id=EVAL_OWNED),
        RUN_VICTIM: _run_row(RUN_VICTIM, evaluation_id=EVAL_VICTIM),
    }
    return experiments, evaluations, runs


def _override_db(app, *, membership=None) -> None:
    experiments, evaluations, runs = _world()
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db_session] = lambda: _StubSession(
        membership=membership,
        experiments=experiments,
        evaluations=evaluations,
        runs=runs,
    )


def _request(client, method, path, body):
    if body is None:
        return getattr(client, method)(path)
    if method == "get":
        return getattr(client, method)(path, params=body)
    return getattr(client, method)(path, json=body)


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_unauthenticated_is_rejected(client, method, path, body):
    assert _request(client, method, path, body).status_code == 401


def test_unauthenticated_create_and_list_rejected(client):
    assert client.post("/api/v1/experiments", json={"name": "x"}).status_code == 401
    assert client.get("/api/v1/experiments").status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_cross_tenant_experiment_is_forbidden(app, client, method, path, body):
    _override_db(app, membership=_membership_row())
    assert _request(client, method, path, body).status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_non_member_is_forbidden(app, client, method, path, body):
    owned_path = path.replace(EXP_VICTIM, EXP_DRAFT)
    _override_db(app, membership=None)
    assert _request(client, method, owned_path, body).status_code == 403


def test_non_member_create_and_list_forbidden(app, client):
    _override_db(app, membership=None)
    assert client.post("/api/v1/experiments", json={"name": "x"}).status_code == 403
    assert client.get("/api/v1/experiments").status_code == 403


def test_member_can_crud_own_experiment(app, client):
    _override_db(app, membership=_membership_row())
    assert client.get(f"/api/v1/experiments/{EXP_DRAFT}").status_code == 200
    assert (
        client.patch(
            f"/api/v1/experiments/{EXP_DRAFT}", json={"description": "mine"}
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/experiments/{EXP_DRAFT}/activate").status_code == 200
    assert client.post(f"/api/v1/experiments/{EXP_ACTIVE}/complete").status_code == 200
    assert client.post(f"/api/v1/experiments/{EXP_ACTIVE}/archive").status_code == 200
    assert client.delete(f"/api/v1/experiments/{EXP_DRAFT}").status_code == 204


def test_member_can_create_and_list_own(app, client):
    _override_db(app, membership=_membership_row())
    created = client.post("/api/v1/experiments", json={"name": "mine"})
    assert created.status_code == 201
    assert created.json()["project_id"] == ORG
    listed = client.get("/api/v1/experiments").json()
    assert {item["id"] for item in listed["items"]} == {EXP_DRAFT, EXP_ACTIVE}
    assert listed["total"] == 2


def test_nonexistent_experiment_is_truthful(app, client):
    _override_db(app, membership=_membership_row())
    missing = "00000000-0000-0000-0000-0000000000ef"
    assert client.get(f"/api/v1/experiments/{missing}").status_code == 404
    assert client.get("/api/v1/experiments/not-a-uuid").status_code == 404


def test_baseline_foreign_run_denied(app, client):
    _override_db(app, membership=_membership_row())
    response = client.post(
        f"/api/v1/experiments/{EXP_DRAFT}/baseline", json={"run_id": RUN_VICTIM}
    )
    assert response.status_code == 403


def test_baseline_nonexistent_and_malformed_run_truthful(app, client):
    _override_db(app, membership=_membership_row())
    missing = "00000000-0000-0000-0000-0000000000df"
    assert (
        client.post(
            f"/api/v1/experiments/{EXP_DRAFT}/baseline", json={"run_id": missing}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/experiments/{EXP_DRAFT}/baseline", json={"run_id": "not-a-uuid"}
        ).status_code
        == 404
    )


def test_baseline_own_run_succeeds(app, client):
    _override_db(app, membership=_membership_row())
    response = client.post(
        f"/api/v1/experiments/{EXP_DRAFT}/baseline", json={"run_id": RUN_OWNED}
    )
    assert response.status_code == 200
    assert response.json()["baseline_run_id"] == RUN_OWNED


def test_analytics_experiment_comparison_foreign_denied(app, client):
    _override_db(app, membership=_membership_row())
    response = client.get(
        "/api/v1/analytics/experiment-comparison",
        params={"experiment_id": EXP_VICTIM},
    )
    assert response.status_code == 403
