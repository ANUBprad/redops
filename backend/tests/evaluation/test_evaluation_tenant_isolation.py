"""Regression tests: evaluation routes are tenant-scoped.

Every ``/evaluations`` endpoint historically relied on ``get_current_user``
only, letting any authenticated user list every organization's evaluations,
fetch/modify/delete them by id, and create evaluations attributed to an
arbitrary ``project_id``/``created_by`` (cross-tenant broken object-level
authorization).

The fix:
  - ``create_evaluation`` derives ``project_id`` from the caller's JWT org
    and ``created_by`` from the authenticated user; body fields are ignored.
  - ``list_evaluations`` always filters by the caller's JWT org.
  - every by-id route runs the shared ``require_owned_evaluation`` gate
    (membership revalidation + ``project_id == org_id`` assertion).

These tests run the real dependency chain - only ``get_db_session`` is
replaced by a stub returning ORM rows - so removing the gate from any route
fails the cross-tenant assertions. The other arg parsing/eval surface
(PATCH /metrics/evaluations/{id}/enabled-metrics) is covered here too via
``configure_evaluation_metrics``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.tenant import MembershipModel

ORG = "org-acme"
OTHER_ORG = "org-rival"
EVAL_ID = "00000000-0000-0000-0000-00000000000c"
USER = CurrentUser(user_id="user-attacker", org_id=ORG)

BY_ID_ROUTES = [
    ("get", f"/api/v1/evaluations/{EVAL_ID}", None),
    ("patch", f"/api/v1/evaluations/{EVAL_ID}", {"description": "tampered"}),
    ("delete", f"/api/v1/evaluations/{EVAL_ID}", None),
    ("post", f"/api/v1/evaluations/{EVAL_ID}/duplicate", {"name": "copy"}),
    ("post", f"/api/v1/evaluations/{EVAL_ID}/archive", None),
    ("post", f"/api/v1/evaluations/{EVAL_ID}/ready", None),
    ("patch", f"/api/v1/metrics/evaluations/{EVAL_ID}/enabled-metrics", {"metric_names": ["accuracy"]}),
]

CREATE_BODY = {
    "project_id": OTHER_ORG,  # spoofed tenant; must be ignored
    "name": "poisoned-evaluation",
    "provider": "openai",
    "model": "gpt-4o",
    "metrics": ["accuracy"],
    "configuration": {"max_tokens": 100},
}


class _StubScalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _StubResult:
    def __init__(self, value):
        self._single = value if not isinstance(value, list) else None
        self._multi = [] if value is None else (value if isinstance(value, list) else [value])

    def scalar_one_or_none(self):
        return self._single

    def scalar_one(self):
        return self._single

    def scalar(self):
        if self._single is None:
            raise AssertionError("scalar() called with no value")
        return self._single

    def scalars(self):
        return _StubScalars(self._multi)


class _StubSession:
    """Routes compiled SQL to the stub membership/evaluation rows."""

    def __init__(self, *, membership=None, evaluations=None, count=1):
        self._membership = membership
        self._evaluations = evaluations
        self._count = count

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        if "memberships" in sql:
            return _StubResult(self._membership)
        if "evaluations" in sql:
            if "count(" in sql:
                return _StubResult(self._count)
            if "evaluations.id =" in sql:
                return _StubResult(self._evaluations)
            if "limit" in sql:
                return _StubResult(self._evaluations)
            return _StubResult(None)
        return _StubResult(None)

    def add(self, _model):
        pass

    async def merge(self, _model):
        pass

    async def delete(self, _model):
        pass

    async def flush(self):
        pass


def _override_db(app, *, membership=None, evaluations=None, count=1):
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db_session] = lambda: _StubSession(
        membership=membership,
        evaluations=evaluations,
        count=count,
    )


def _membership_row() -> MembershipModel:
    return MembershipModel(
        id="00000000-0000-0000-0000-00000000000d",
        user_id=USER.user_id,
        organization_id=ORG,
        role="member",
        invited_by="user-owner",
        is_active=True,
        joined_at=datetime.now(UTC),
    )


def _evaluation_row(*, project_id: str = ORG) -> EvaluationModel:
    now = datetime.now(UTC)
    return EvaluationModel(
        id=EVAL_ID,
        project_id=project_id,
        dataset_id=None,
        name="victim-evaluation",
        description="secret config",
        provider="openai",
        model="gpt-4o",
        metrics=["accuracy"],
        tags=["internal"],
        configuration={"max_tokens": 500},
        status="draft",
        created_by="user-owner",
        version=1,
        created_at=now,
        updated_at=now,
    )


def _request(client, method, path, body):
    if body is None:
        return getattr(client, method)(path)
    return getattr(client, method)(path, json=body)


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_unauthenticated_is_rejected(client, method, path, body):
    response = _request(client, method, path, body)
    assert response.status_code == 401


def test_unauthenticated_create_and_list_rejected(client):
    assert client.post("/api/v1/evaluations", json=CREATE_BODY).status_code == 401
    assert client.get("/api/v1/evaluations").status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_cross_tenant_evaluation_is_forbidden(app, client, method, path, body):
    _override_db(
        app,
        membership=_membership_row(),
        evaluations=_evaluation_row(project_id=OTHER_ORG),
    )
    response = _request(client, method, path, body)
    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), BY_ID_ROUTES)
def test_non_member_is_forbidden(app, client, method, path, body):
    _override_db(app, membership=None, evaluations=_evaluation_row())
    response = _request(client, method, path, body)
    assert response.status_code == 403


def test_non_member_create_and_list_forbidden(app, client):
    _override_db(app, membership=None)
    assert client.post("/api/v1/evaluations", json=CREATE_BODY).status_code == 403
    assert client.get("/api/v1/evaluations").status_code == 403


def test_member_can_create_evaluation(app, client):
    _override_db(app, membership=_membership_row())
    response = client.post("/api/v1/evaluations", json=CREATE_BODY)
    assert response.status_code == 201
    payload = response.json()
    assert payload["project_id"] == ORG
    assert payload["created_by"] == USER.user_id


def test_member_can_list_own_org_evaluations(app, client):
    _override_db(
        app,
        membership=_membership_row(),
        evaluations=[_evaluation_row()],
        count=1,
    )
    response = client.get("/api/v1/evaluations")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["project_id"] == ORG


def test_member_can_get_evaluation(app, client):
    _override_db(app, membership=_membership_row(), evaluations=_evaluation_row())
    response = client.get(f"/api/v1/evaluations/{EVAL_ID}")
    assert response.status_code == 200
    assert response.json()["project_id"] == ORG


def test_member_can_update_description(app, client):
    _override_db(app, membership=_membership_row(), evaluations=_evaluation_row())
    response = client.patch(
        f"/api/v1/evaluations/{EVAL_ID}",
        json={"description": "updated by member"},
    )
    assert response.status_code == 200


def test_member_can_delete_evaluation(app, client):
    _override_db(app, membership=_membership_row(), evaluations=_evaluation_row())
    response = client.delete(f"/api/v1/evaluations/{EVAL_ID}")
    assert response.status_code == 204


def test_member_can_duplicate_evaluation(app, client):
    _override_db(app, membership=_membership_row(), evaluations=_evaluation_row())
    response = client.post(
        f"/api/v1/evaluations/{EVAL_ID}/duplicate",
        json={"name": "copy"},
    )
    assert response.status_code == 201


def test_member_can_archive_evaluation(app, client):
    _override_db(app, membership=_membership_row(), evaluations=_evaluation_row())
    response = client.post(f"/api/v1/evaluations/{EVAL_ID}/archive")
    assert response.status_code == 200


def test_member_can_mark_ready(app, client):
    _override_db(app, membership=_membership_row(), evaluations=_evaluation_row())
    response = client.post(f"/api/v1/evaluations/{EVAL_ID}/ready")
    assert response.status_code == 200


def test_member_can_configure_evaluation_metrics(app, client):
    _override_db(app, membership=_membership_row(), evaluations=_evaluation_row())
    response = client.patch(
        f"/api/v1/metrics/evaluations/{EVAL_ID}/enabled-metrics",
        json={"metric_names": ["accuracy", "latency"]},
    )
    assert response.status_code == 200