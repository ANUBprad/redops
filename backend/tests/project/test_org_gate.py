"""Regression tests: org-scoped project routes enforce membership.

The five ``/orgs/{org_id}/projects`` endpoints historically relied on
authentication only (``get_current_user``), letting any authenticated user
read, create, modify, or delete projects in any organization by supplying
that organization's id in the path (cross-tenant broken object-level
authorization).

The fix wires the shared ``require_org_membership`` dependency onto every
route. These tests run the real dependency chain - only the DB-backed
``get_db_session`` seam is replaced with an in-memory stub that returns
ORM rows like a real database would - so removing the gate from any route
fails the cross-tenant assertions.
"""

from datetime import UTC, datetime

import pytest

from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.models.project import ProjectModel
from app.infrastructure.database.models.tenant import MembershipModel

ORG = "org-acme"
PROJECT_ID = "00000000-0000-0000-0000-00000000000a"
USER = CurrentUser(user_id="user-attacker")

PROJECT_ROUTES = [
    ("post", f"/api/v1/orgs/{ORG}/projects", {"name": "project-x"}),
    ("get", f"/api/v1/orgs/{ORG}/projects", None),
    ("get", f"/api/v1/orgs/{ORG}/projects/{PROJECT_ID}", None),
    ("patch", f"/api/v1/orgs/{ORG}/projects/{PROJECT_ID}", {"name": "project-y"}),
    ("delete", f"/api/v1/orgs/{ORG}/projects/{PROJECT_ID}", None),
]


class _StubScalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _StubResult:
    """Mimics the small surface of an AsyncResult used by the repositories."""

    def __init__(self, value):
        self._single = value if not isinstance(value, list) else None
        self._multi = [] if value is None else (value if isinstance(value, list) else [value])

    def scalar_one_or_none(self):
        return self._single

    def scalar(self):
        if self._single is None:
            raise AssertionError("scalar() called with no value")
        return self._single

    def scalars(self):
        return _StubScalars(self._multi)


class _StubSession:
    """Minimal session that routes queries to the stub membership/project rows.

    Instances of the two ORM models below are cheap in-memory objects (no
    engine required), which lets the real repository ``_to_domain`` mapping
    and the real ``require_org_membership`` logic execute end to end.
    """

    def __init__(self, *, membership=None, projects=None):
        self._membership = membership
        self._projects = projects

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        if "memberships" in sql:
            return _StubResult(self._membership)
        return _StubResult(self._projects)

    def add(self, _model):
        pass


def _override_db(app, *, membership=None, projects=None):
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db_session] = lambda: _StubSession(
        membership=membership,
        projects=projects,
    )


def _membership_row() -> MembershipModel:
    return MembershipModel(
        id="00000000-0000-0000-0000-00000000000b",
        user_id=USER.user_id,
        organization_id=ORG,
        role="member",
        invited_by="user-owner",
        is_active=True,
        joined_at=datetime.now(UTC),
    )


def _project_row() -> ProjectModel:
    now = datetime.now(UTC)
    return ProjectModel(
        id=PROJECT_ID,
        name="project-x",
        description=None,
        organization_id=ORG,
        created_by="user-owner",
        is_active=True,
        version=1,
        created_at=now,
        updated_at=now,
    )


def _request(client, method, path, body):
    if body is None:
        return getattr(client, method)(path)
    return getattr(client, method)(path, json=body)


@pytest.mark.parametrize(("method", "path", "body"), PROJECT_ROUTES)
def test_unauthenticated_is_rejected(client, method, path, body):
    response = _request(client, method, path, body)
    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), PROJECT_ROUTES)
def test_cross_tenant_non_member_is_forbidden(app, client, method, path, body):
    _override_db(app, membership=None)
    response = _request(client, method, path, body)
    assert response.status_code == 403


def test_member_can_create_project(app, client):
    _override_db(app, membership=_membership_row())
    response = client.post(f"/api/v1/orgs/{ORG}/projects", json={"name": "project-x"})
    assert response.status_code == 201
    assert response.json()["organization_id"] == ORG


def test_member_can_list_projects(app, client):
    _override_db(app, membership=_membership_row(), projects=[_project_row()])
    response = client.get(f"/api/v1/orgs/{ORG}/projects")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["organization_id"] == ORG


def test_member_can_get_project(app, client):
    _override_db(app, membership=_membership_row(), projects=_project_row())
    response = client.get(f"/api/v1/orgs/{ORG}/projects/{PROJECT_ID}")
    assert response.status_code == 200
    assert response.json()["organization_id"] == ORG


def test_member_can_update_project(app, client):
    _override_db(app, membership=_membership_row(), projects=_project_row())
    response = client.patch(
        f"/api/v1/orgs/{ORG}/projects/{PROJECT_ID}",
        json={"name": "project-y"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "project-y"


def test_member_can_delete_project(app, client):
    _override_db(app, membership=_membership_row(), projects=_project_row())
    response = client.delete(f"/api/v1/orgs/{ORG}/projects/{PROJECT_ID}")
    assert response.status_code == 204
