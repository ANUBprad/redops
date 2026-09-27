"""Regression tests: agent definition/run tenant isolation (S-09).

Forensic audit found both agent surfaces in the pre-S-03/S-04 state:

* Agent DEFINITIONS mirror pre-S-03 evaluations exactly: create takes
  body ``project_id``/``created_by`` (spoofable), list filters by a
  caller ``project_id``, and six by-id routes (get/patch/delete/
  activate/deactivate/archive) check nothing — cross-tenant read,
  mutate, transition and delete.
* Agent RUNS mirror pre-S-04/S-05 evaluation runs: create persists an
  unattested ``agent_definition_id`` plus a spoofable ``project_id``
  and schedules the Temporal/provider execution before any ownership
  concept; get/cancel/retry/list check nothing. Cancel signals a
  foreign Temporal workflow; retry clones foreign runs.

The fix mirrors the established primitives with the agent tenant key
(``AgentDefinition.project_id``):
  - ``require_owned_agent_definition``: membership + project match;
    unknown/malformed truthfully 404; cross-tenant 403.
  - create/list definitions via ``require_current_org_membership``
    (project/created_by server-derived; legacy client filter ignored).
  - ``require_owned_agent_run``: resolve run -> parent definition ->
    delegate; orphan runs (NULL definition, legal at create) fall back
    to persisted ``metadata.project_id``.
  - run create attests a supplied definition before persistence and
    Temporal work; run list scopes via ``AgentRunQuery.owner_project_id``
    (owned definitions + own orphans); cancel/retry gate before any
    Temporal/persistence side effect.

No agent streaming/trace/message endpoints exist (only run summaries),
so there is no separate stream surface to gate. Real dependency chain
with a stub session throughout.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.domain.enums.agent_enums import AgentStatus
from app.agents.domain.enums.agent_enums import AgentRunStatus
from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.infrastructure.database.models.agent_definition import AgentDefinitionModel
from app.infrastructure.database.models.agent_run import AgentRunModel
from app.infrastructure.database.models.tenant import MembershipModel

ORG = "org-acme"
OTHER_ORG = "org-rival"
AGENT_ACTIVE = "00000000-0000-0000-0000-0000000000a1"
AGENT_INACTIVE = "00000000-0000-0000-0000-0000000000a2"
AGENT_VICTIM = "00000000-0000-0000-0000-0000000000a3"
RUN_LINKED = "00000000-0000-0000-0000-0000000000b1"
RUN_FAILED = "00000000-0000-0000-0000-0000000000b2"
RUN_VICTIM = "00000000-0000-0000-0000-0000000000b3"
RUN_VICTIM_FAILED = "00000000-0000-0000-0000-0000000000b4"
RUN_ORPHAN = "00000000-0000-0000-0000-0000000000b5"
USER = CurrentUser(user_id="user-attacker", org_id=ORG)
NOW = datetime.now(UTC)

AGENT_BY_ID_ROUTES = [
    ("get", f"/api/v1/agents/{AGENT_VICTIM}", None),
    ("patch", f"/api/v1/agents/{AGENT_VICTIM}", {"description": "tampered"}),
    ("delete", f"/api/v1/agents/{AGENT_VICTIM}", None),
    ("post", f"/api/v1/agents/{AGENT_VICTIM}/activate", None),
    ("post", f"/api/v1/agents/{AGENT_VICTIM}/deactivate", None),
    ("post", f"/api/v1/agents/{AGENT_VICTIM}/archive", None),
]

RUN_BY_ID_ROUTES = [
    ("get", f"/api/v1/agent-runs/{RUN_VICTIM}", None),
    ("post", f"/api/v1/agent-runs/{RUN_VICTIM}/cancel", {"reason": "user_cancelled"}),
    ("post", f"/api/v1/agent-runs/{RUN_VICTIM_FAILED}/retry", None),
]

CREATE_AGENT_BODY = {
    "project_id": OTHER_ORG,
    "name": "poisoned-agent",
    "agent_type": "llm",
    "model": "gpt-4o",
    "provider": "openai",
    "created_by": "spoofed-user",
}

CREATE_RUN_BODY = {
    "agent_name": "run",
    "agent_definition_id": AGENT_ACTIVE,
    "provider": "openai",
    "model": "gpt-4o",
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


class _StubSession:
    def __init__(self, *, membership=None, agents=None, runs=None):
        self._membership = membership
        self._agents = agents or {}
        self._runs = runs or {}
        self._saved: dict[str, object] = {}
        self.merged: list[object] = []

    @staticmethod
    def _which(sql: str, mapping: dict):
        for key, row in mapping.items():
            if key.lower() in sql:
                return row
        return None

    def _run_in_scope(self, row: AgentRunModel) -> bool:
        if row.agent_definition_id:
            agent = self._agents.get(row.agent_definition_id)
            return agent is not None and agent.project_id == ORG
        return (row.metadata_ or {}).get("project_id") == ORG

    def _scoped_runs(self, sql: str) -> list:
        rows = [r for r in self._runs.values() if self._run_in_scope(r)]
        match = re.search(r"agent_runs\.status = '([^']+)'", sql)
        if match is not None:
            rows = [r for r in rows if r.status == match.group(1)]
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
        if "agent_runs" in sql:
            if "count(" in sql:
                if "join" in sql:
                    return _StubResult(None, count=len(self._scoped_runs(sql)))
                return _StubResult(None, count=len(self._runs))
            if "limit" in sql:
                if "join" in sql:
                    return _StubResult(self._scoped_runs(sql))
                return _StubResult(list(self._runs.values()))
            row = self._which(sql, self._runs)
            if row is None:
                row = self._which(sql, self._saved)
            return _StubResult(row)
        if "agent_definitions" in sql:
            project = re.search(r"agent_definitions\.project_id = '([^']+)'", sql)
            rows = list(self._agents.values())
            if project is not None:
                rows = [r for r in rows if r.project_id == project.group(1)]
            if "count(" in sql:
                return _StubResult(None, count=len(rows))
            if "limit" in sql:
                return _StubResult(rows)
            return _StubResult(self._which(sql, self._agents))
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
        joined_at=NOW,
    )


def _agent_row(agent_id: str, *, project_id: str, status: str) -> AgentDefinitionModel:
    return AgentDefinitionModel(
        id=agent_id,
        project_id=project_id,
        name="agent",
        description="",
        agent_type="llm",
        model="gpt-4o",
        provider="openai",
        capabilities=[],
        config={},
        endpoint=None,
        status=status,
        created_by="user-owner",
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _run_row(
    run_id: str,
    *,
    agent_definition_id: str | None,
    project_id: str | None = None,
    status: str = "running",
) -> AgentRunModel:
    return AgentRunModel(
        id=run_id,
        agent_definition_id=agent_definition_id,
        agent_name="agent",
        workflow_id="wf-1",
        provider="openai",
        model="gpt-4o",
        status=status,
        priority="normal",
        steps_total=3,
        steps_completed=0,
        steps_failed=0,
        token_input=0,
        token_output=0,
        cost=0.0,
        average_latency_ms=0,
        failure_reason=None,
        config={
            "profile": {"provider_name": "openai", "model_id": "gpt-4o"},
        },
        metadata_={"project_id": project_id},
        started_at=NOW,
        completed_at=None,
        cancelled_at=None,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _world() -> tuple[dict, dict]:
    agents = {
        AGENT_ACTIVE: _agent_row(
            AGENT_ACTIVE, project_id=ORG, status=AgentStatus.ACTIVE.value
        ),
        AGENT_INACTIVE: _agent_row(
            AGENT_INACTIVE, project_id=ORG, status=AgentStatus.INACTIVE.value
        ),
        AGENT_VICTIM: _agent_row(
            AGENT_VICTIM, project_id=OTHER_ORG, status=AgentStatus.ACTIVE.value
        ),
    }
    runs = {
        RUN_LINKED: _run_row(
            RUN_LINKED,
            agent_definition_id=AGENT_ACTIVE,
            status=AgentRunStatus.RUNNING.value,
        ),
        RUN_FAILED: _run_row(
            RUN_FAILED,
            agent_definition_id=AGENT_ACTIVE,
            status=AgentRunStatus.FAILED.value,
        ),
        RUN_VICTIM: _run_row(
            RUN_VICTIM,
            agent_definition_id=AGENT_VICTIM,
            status=AgentRunStatus.RUNNING.value,
        ),
        RUN_VICTIM_FAILED: _run_row(
            RUN_VICTIM_FAILED,
            agent_definition_id=AGENT_VICTIM,
            status=AgentRunStatus.FAILED.value,
        ),
        RUN_ORPHAN: _run_row(
            RUN_ORPHAN,
            agent_definition_id=None,
            project_id=ORG,
            status=AgentRunStatus.RUNNING.value,
        ),
    }
    return agents, runs


def _override_db(app, *, membership=None) -> _StubSession:
    agents, runs = _world()
    session = _StubSession(membership=membership, agents=agents, runs=runs)
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


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body"), AGENT_BY_ID_ROUTES)
def test_unauthenticated_agent_rejected(client, method, path, body):
    assert _request(client, method, path, body).status_code == 401


def test_unauthenticated_agent_create_and_list_rejected(client):
    assert client.post("/api/v1/agents", json=CREATE_AGENT_BODY).status_code == 401
    assert client.get("/api/v1/agents").status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), AGENT_BY_ID_ROUTES)
def test_cross_tenant_agent_is_forbidden(app, client, method, path, body):
    _override_db(app, membership=_membership_row())
    assert _request(client, method, path, body).status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), AGENT_BY_ID_ROUTES)
def test_non_member_agent_is_forbidden(app, client, method, path, body):
    owned_path = path.replace(AGENT_VICTIM, AGENT_ACTIVE)
    _override_db(app, membership=None)
    assert _request(client, method, owned_path, body).status_code == 403


def test_non_member_agent_create_and_list_forbidden(app, client):
    _override_db(app, membership=None)
    assert client.post("/api/v1/agents", json=CREATE_AGENT_BODY).status_code == 403
    assert client.get("/api/v1/agents").status_code == 403


def test_member_agent_crud_lifecycle(app, client):
    _override_db(app, membership=_membership_row())
    assert client.get(f"/api/v1/agents/{AGENT_ACTIVE}").status_code == 200
    assert (
        client.patch(
            f"/api/v1/agents/{AGENT_ACTIVE}", json={"description": "mine"}
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/agents/{AGENT_INACTIVE}/activate").status_code == 200
    assert client.post(f"/api/v1/agents/{AGENT_ACTIVE}/deactivate").status_code == 200
    assert client.post(f"/api/v1/agents/{AGENT_ACTIVE}/archive").status_code == 200
    assert client.delete(f"/api/v1/agents/{AGENT_ACTIVE}").status_code == 204


def test_member_agent_create_attributes_caller_org(app, client):
    _override_db(app, membership=_membership_row())
    response = client.post("/api/v1/agents", json=CREATE_AGENT_BODY)
    assert response.status_code == 201
    payload = response.json()
    assert payload["project_id"] == ORG
    assert payload["created_by"] == USER.user_id


def test_member_agent_list_only_own(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/agents").json()
    assert {item["id"] for item in payload["items"]} == {AGENT_ACTIVE, AGENT_INACTIVE}
    assert payload["total"] == 2


def test_nonexistent_agent_is_truthful(app, client):
    _override_db(app, membership=_membership_row())
    missing = "00000000-0000-0000-0000-0000000000af"
    assert client.get(f"/api/v1/agents/{missing}").status_code == 404
    assert client.get("/api/v1/agents/not-a-uuid").status_code == 404


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body"), RUN_BY_ID_ROUTES)
def test_unauthenticated_run_rejected(client, method, path, body):
    assert _request(client, method, path, body).status_code == 401


def test_unauthenticated_run_create_and_list_rejected(client):
    assert client.post("/api/v1/agent-runs", json=CREATE_RUN_BODY).status_code == 401
    assert client.get("/api/v1/agent-runs").status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), RUN_BY_ID_ROUTES)
def test_cross_tenant_run_is_forbidden(app, client, method, path, body):
    _override_db(app, membership=_membership_row())
    assert _request(client, method, path, body).status_code == 403


def test_cross_tenant_run_list_excludes_foreign(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/agent-runs").json()
    assert {item["id"] for item in payload["items"]} == {RUN_LINKED, RUN_FAILED, RUN_ORPHAN}
    assert payload["total"] == 3


def test_non_member_run_is_forbidden(app, client):
    _override_db(app, membership=None)
    assert client.get(f"/api/v1/agent-runs/{RUN_LINKED}").status_code == 403
    assert client.get("/api/v1/agent-runs").status_code == 403
    assert client.post("/api/v1/agent-runs", json=CREATE_RUN_BODY).status_code == 403


def test_cross_tenant_cancel_signals_nothing(app, client, temporal_mock):
    _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    handle = temporal_mock.get_workflow_handle.return_value
    response = client.post(
        f"/api/v1/agent-runs/{RUN_VICTIM}/cancel", json={"reason": "user_cancelled"}
    )
    assert response.status_code == 403
    handle.signal.assert_not_called()


def test_same_tenant_run_lifecycle(app, client, temporal_mock):
    _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    assert client.get(f"/api/v1/agent-runs/{RUN_LINKED}").status_code == 200
    assert client.post(f"/api/v1/agent-runs/{RUN_LINKED}/cancel", json={"reason": "user_cancelled"}).status_code == 200
    assert client.post(f"/api/v1/agent-runs/{RUN_FAILED}/retry").status_code == 201
    temporal_mock.get_workflow_handle.assert_called_once()


def test_create_run_foreign_definition_denied_no_persistence(app, client, temporal_mock):
    session = _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    response = client.post(
        "/api/v1/agent-runs",
        json={**CREATE_RUN_BODY, "agent_definition_id": AGENT_VICTIM},
    )
    assert response.status_code == 403
    temporal_mock.start_workflow.assert_not_called()
    assert session.merged == []


def test_create_run_nonexistent_and_malformed_definition_truthful(
    app, client, temporal_mock
):
    _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    missing = "00000000-0000-0000-0000-0000000000bf"
    assert (
        client.post(
            "/api/v1/agent-runs", json={**CREATE_RUN_BODY, "agent_definition_id": missing}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/agent-runs",
            json={**CREATE_RUN_BODY, "agent_definition_id": "not-a-uuid"},
        ).status_code
        == 404
    )
    temporal_mock.start_workflow.assert_not_called()


def test_create_run_project_spoof_is_ignored(app, client, temporal_mock):
    session = _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    body = {**CREATE_RUN_BODY, "project_id": OTHER_ORG}
    assert client.post("/api/v1/agent-runs", json=body).status_code == 201
    assert session.merged[0].metadata_["project_id"] == ORG
    temporal_mock.start_workflow.assert_called_once()


def test_create_run_orphan_attributes_caller_org(app, client, temporal_mock):
    session = _override_db(app, membership=_membership_row())
    _override_temporal(app, temporal_mock)
    body = {k: v for k, v in CREATE_RUN_BODY.items() if k != "agent_definition_id"}
    response = client.post("/api/v1/agent-runs", json=body)
    assert response.status_code == 201
    assert response.json()["agent_definition_id"] is None
    assert session.merged[0].metadata_["project_id"] == ORG


def test_nonexistent_run_is_truthful(app, client):
    _override_db(app, membership=_membership_row())
    missing = "00000000-0000-0000-0000-0000000000bf"
    assert client.get(f"/api/v1/agent-runs/{missing}").status_code == 404
    assert client.get("/api/v1/agent-runs/not-a-uuid").status_code == 404


def test_orphan_run_targeted_access_preserved(app, client):
    """Unlinked runs carry no attribution: targeted access stays working.

    Locked as the documented residual exactly like S-08's AttackRun
    orphans: the scoped list excludes them (enumeration fails closed).
    """
    _override_db(app, membership=_membership_row())
    assert client.get(f"/api/v1/agent-runs/{RUN_ORPHAN}").status_code == 200
