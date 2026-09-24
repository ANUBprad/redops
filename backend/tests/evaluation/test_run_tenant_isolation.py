"""Regression tests: run-keyed raw LLM-I/O routes are tenant-scoped (S-04).

Every ``/runs/{run_id}``, ``/metrics/runs/{run_id}/*``,
``/replay/*/<run_id>`` and ``/runs/{run_id}/events|logs`` endpoint
historically relied on ``get_current_user`` only, letting any authenticated
user read another organization's stored prompts, provider responses, metric
``raw_output``/reasoning, traces and timeline/logs by brute-forcing run ids
— and mutate foreign runs (cancel/retry re-executes persisted prompts via
Temporal, trace delete wipes evidence, log writes forge timeline entries).

The fix adds the shared ``require_owned_run`` gate
(``backend/app/core/dependencies.py``): resolve the run -> obtain its parent
``evaluation_id`` -> delegate to ``require_owned_evaluation``, preserving the
single existing tenant/ownership choke point. Runs without a parent
evaluation fall back to the run's persisted ``metadata.project_id``.
``GET /runs/evaluation/{evaluation_id}`` is gated with
``require_owned_evaluation`` directly (evaluation id is in the path).

These tests run the real dependency chain — only ``get_db_session`` (plus
``get_temporal_client`` for cancel/retry) is stubbed — so removing the gate
from any route fails the cross-tenant assertions.

Explicitly out of scope (classified, not gated):
  - ``POST /metrics/score`` / ``score-batch``: ad-hoc compute flow; the
    body ``run_id`` is an unattested label by design (existing tests score
    with never-persisted ids and expect 200). Gating would break that flow.
  - ``GET /runs`` list / ``POST /runs`` create attribution: cross-tenant
    enumeration + tenant spoofing need new evaluation-join scoping logic;
    follow-up work, not the ``require_owned_run`` boundary.
  - analytics run-filtered reads, experiment ``set_baseline``,
    redteam/agent-run surfaces: separate aggregates needing their own
    ownership mapping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.replay import get_replay_service
from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.evaluation.replay.service import ReplayService
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.tenant import MembershipModel

ORG = "org-acme"
OTHER_ORG = "org-rival"
EVAL_OWNED = "00000000-0000-0000-0000-0000000000c1"
EVAL_VICTIM = "00000000-0000-0000-0000-0000000000c2"
RUN_OWNED = "00000000-0000-0000-0000-0000000000d1"
RUN_VICTIM = "00000000-0000-0000-0000-0000000000d2"
RUN_ORPHAN = "00000000-0000-0000-0000-0000000000d3"
ITEM_ID = "00000000-0000-0000-0000-0000000000e1"
USER = CurrentUser(user_id="user-attacker", org_id=ORG)

TRACE = {
    "run_id": RUN_OWNED,
    "evaluation_name": "owned-eval",
    "provider_name": "openai",
    "model_id": "gpt-4o",
    "status": "completed",
    "events": [],
    "item_traces": [
        {
            "item_index": 0,
            "prompt_trace": {"prompt": "owned secret prompt"},
            "provider_trace": None,
            "metric_traces": [
                {
                    "metric_name": "accuracy",
                    "score": 1.0,
                    "normalized_score": 1.0,
                }
            ],
            "total_latency_ms": 10,
            "total_cost_usd": 0.001,
            "error": None,
        }
    ],
    "aggregated_metrics": {"accuracy": {"mean": 1.0}},
    "configuration": {"provider": "openai", "model": "gpt-4o"},
    "total_cost_usd": 0.001,
    "total_tokens_input": 5,
    "total_tokens_output": 5,
    "total_latency_ms": 10,
    "error": None,
}

GET_ROUTES = [
    ("get", f"/api/v1/runs/{RUN_VICTIM}", None),
    ("get", f"/api/v1/metrics/runs/{RUN_VICTIM}/results", None),
    ("get", f"/api/v1/metrics/runs/{RUN_VICTIM}/scores", None),
    ("get", f"/api/v1/metrics/runs/{RUN_VICTIM}/items/{ITEM_ID}/results", None),
    ("get", f"/api/v1/replay/traces/{RUN_VICTIM}", None),
    ("get", f"/api/v1/replay/traces/{RUN_VICTIM}/report", None),
    ("get", f"/api/v1/replay/compare/{RUN_VICTIM}/{RUN_VICTIM}", None),
    ("get", f"/api/v1/replay/regression/{RUN_VICTIM}/{RUN_VICTIM}", None),
    ("get", f"/api/v1/runs/{RUN_VICTIM}/events", None),
    ("get", f"/api/v1/runs/{RUN_VICTIM}/events/stream", None),
    ("get", f"/api/v1/runs/{RUN_VICTIM}/progress/stream", None),
    ("get", f"/api/v1/runs/{RUN_VICTIM}/logs", None),
    ("get", f"/api/v1/runs/evaluation/{EVAL_VICTIM}", None),
    ("post", f"/api/v1/runs/{RUN_VICTIM}/cancel", {"reason": "user_cancelled"}),
    ("post", f"/api/v1/runs/{RUN_VICTIM}/retry", None),
    ("post", f"/api/v1/runs/{RUN_VICTIM}/logs", {"level": "INFO", "source": "t", "message": "forged"}),
    ("delete", f"/api/v1/replay/traces/{RUN_VICTIM}", None),
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
    """Routes compiled SQL to stub membership/evaluation/run rows."""

    def __init__(self, *, membership=None, evaluations=None, runs=None, trace=None):
        self._membership = membership
        self._evaluations = evaluations or {}
        self._runs = runs or {}
        self._trace = trace
        self._saved: dict[str, object] = {}

    @staticmethod
    def _which(sql: str, mapping: dict) -> object | None:
        for key, row in mapping.items():
            if key.lower() in sql:
                return row
        return None

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        if "memberships" in sql:
            return _StubResult(self._membership)
        if "metric_results" in sql or "run_events" in sql or "run_logs" in sql:
            if "count(" in sql:
                return _StubResult(None, count=0)
            return _StubResult([])
        if "evaluation_runs" in sql:
            if "evaluation_runs.id" not in sql:
                # DatabaseTraceRepository selects trace_data only.
                return _StubResult(self._trace)
            if "count(" in sql:
                return _StubResult(None, count=len(self._runs))
            if "limit" in sql:
                return _StubResult(list(self._runs.values()))
            row = self._which(sql, self._runs)
            if row is None:
                # Retry persists a brand-new run then re-reads it; serve
                # merged rows so the re-read resolves instead of 404.
                row = self._which(sql, self._saved)
            return _StubResult(row)
        if "evaluations" in sql:
            if "count(" in sql:
                return _StubResult(None, count=len(self._evaluations))
            return _StubResult(self._which(sql, self._evaluations))
        return _StubResult(None)

    def add(self, _model):
        pass

    async def merge(self, model):
        self._saved[str(getattr(model, "id", ""))] = model

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
        description="secret config",
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
    dataset_items: list | None = None,
) -> EvaluationRunModel:
    now = datetime.now(UTC)
    return EvaluationRunModel(
        id=run_id,
        evaluation_id=evaluation_id,
        evaluation_name="eval",
        workflow_id="wf-1",
        provider="openai",
        model="gpt-4o",
        status=status,
        priority="normal",
        items_total=1,
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
            "dataset_items": dataset_items or [],
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


def _owned_world() -> tuple[dict, dict]:
    evaluations = {EVAL_OWNED: _evaluation_row(EVAL_OWNED, project_id=ORG)}
    runs = {RUN_OWNED: _run_row(RUN_OWNED, evaluation_id=EVAL_OWNED, status="running")}
    return evaluations, runs


def _victim_world() -> tuple[dict, dict]:
    evaluations = {EVAL_VICTIM: _evaluation_row(EVAL_VICTIM, project_id=OTHER_ORG)}
    runs = {
        RUN_VICTIM: _run_row(
            RUN_VICTIM,
            evaluation_id=EVAL_VICTIM,
            status="failed",
            dataset_items=[{"prompt": "victim secret prompt"}],
        )
    }
    return evaluations, runs


class _StubTraceRepo:
    """In-memory trace storage; keeps the real ReplayService logic in play."""

    def __init__(self, traces: dict | None = None):
        self._traces = dict(traces or {})

    async def find_by_run_id(self, run_id: str):
        return self._traces.get(run_id)

    async def save(self, run_id: str, trace_data: dict):
        self._traces[run_id] = trace_data

    async def delete(self, run_id: str) -> bool:
        if run_id in self._traces:
            del self._traces[run_id]
            return True
        return False


def _trace_for(run_id: str, prompt: str) -> dict:
    trace = dict(TRACE)
    trace = {**trace, "run_id": run_id}
    item = {**trace["item_traces"][0]}
    item = {**item, "prompt_trace": {"prompt": prompt}}
    trace = {**trace, "item_traces": [item]}
    return trace


def _override_db(app, *, membership=None, evaluations=None, runs=None):
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db_session] = lambda: _StubSession(
        membership=membership,
        evaluations=evaluations,
        runs=runs,
    )
    # Victim traces stay present in storage so the pre-fix suite proves the
    # leak (200 with foreign raw I/O) instead of a misleading 404.
    traces = {}
    if runs and RUN_OWNED in runs:
        traces[RUN_OWNED] = TRACE
    if runs and RUN_VICTIM in runs:
        traces[RUN_VICTIM] = _trace_for(RUN_VICTIM, "victim secret prompt")
    app.dependency_overrides[get_replay_service] = lambda: ReplayService(
        _StubTraceRepo(traces)
    )


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


@pytest.mark.parametrize(("method", "path", "body"), GET_ROUTES)
def test_unauthenticated_is_rejected(client, method, path, body):
    response = _request(client, method, path, body)
    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), GET_ROUTES)
def test_cross_tenant_run_is_forbidden(app, client, method, path, body):
    evaluations, runs = _victim_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    response = _request(client, method, path, body)
    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), GET_ROUTES)
def test_non_member_is_forbidden(app, client, method, path, body):
    # Non-members are denied on runs that exist (owned world); requesting
    # unknown ids would 404 before membership is ever evaluated.
    owned_path = path.replace(RUN_VICTIM, RUN_OWNED).replace(EVAL_VICTIM, EVAL_OWNED)
    evaluations, runs = _owned_world()
    _override_db(app, membership=None, evaluations=evaluations, runs=runs)
    response = _request(client, method, owned_path, body)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/runs/{RUN_OWNED}",
        f"/api/v1/metrics/runs/{RUN_OWNED}/results",
        f"/api/v1/metrics/runs/{RUN_OWNED}/scores",
        f"/api/v1/metrics/runs/{RUN_OWNED}/items/{ITEM_ID}/results",
        f"/api/v1/replay/traces/{RUN_OWNED}",
        f"/api/v1/replay/traces/{RUN_OWNED}/report",
        f"/api/v1/replay/compare/{RUN_OWNED}/{RUN_OWNED}",
        f"/api/v1/replay/regression/{RUN_OWNED}/{RUN_OWNED}",
        f"/api/v1/runs/{RUN_OWNED}/events",
        f"/api/v1/runs/{RUN_OWNED}/logs",
        f"/api/v1/runs/evaluation/{EVAL_OWNED}",
    ],
)
def test_same_tenant_read_succeeds(app, client, path):
    evaluations, runs = _owned_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", f"/api/v1/runs/{RUN_OWNED}", None),
        ("get", f"/api/v1/metrics/runs/{RUN_OWNED}/results", None),
        ("get", f"/api/v1/replay/traces/{RUN_OWNED}", None),
        ("get", f"/api/v1/runs/{RUN_OWNED}/events", None),
        ("get", f"/api/v1/runs/{RUN_OWNED}/logs", None),
        ("post", f"/api/v1/runs/{RUN_OWNED}/cancel", {"reason": "user_cancelled"}),
        ("post", f"/api/v1/runs/{RUN_OWNED}/retry", None),
        ("delete", f"/api/v1/replay/traces/{RUN_OWNED}", None),
    ],
)
def test_nonexistent_run_is_truthful(app, client, method, path, body):
    _override_db(app, membership=_membership_row(), evaluations={}, runs={})
    assert _request(client, method, path, body).status_code == 404


def test_malformed_run_id_is_truthful(app, client):
    evaluations, runs = _owned_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    assert client.get("/api/v1/runs/not-a-uuid").status_code == 404
    assert client.get("/api/v1/runs/not-a-uuid/events").status_code == 404


def test_orphan_run_owned_via_metadata(app, client):
    evaluations, runs = {}, {
        RUN_ORPHAN: _run_row(RUN_ORPHAN, evaluation_id=None, project_id=ORG)
    }
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    assert client.get(f"/api/v1/runs/{RUN_ORPHAN}").status_code == 200


def test_orphan_run_foreign_metadata_forbidden(app, client):
    evaluations, runs = {}, {
        RUN_ORPHAN: _run_row(RUN_ORPHAN, evaluation_id=None, project_id=OTHER_ORG)
    }
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    assert client.get(f"/api/v1/runs/{RUN_ORPHAN}").status_code == 403


def test_mixed_pair_second_foreign_is_forbidden(app, client):
    evaluations_v, runs_v = _victim_world()
    evaluations_o, runs_o = _owned_world()
    _override_db(
        app,
        membership=_membership_row(),
        evaluations={**evaluations_o, **evaluations_v},
        runs={**runs_o, **runs_v},
    )
    assert (
        client.get(f"/api/v1/replay/compare/{RUN_OWNED}/{RUN_VICTIM}").status_code == 403
    )
    assert (
        client.get(
            f"/api/v1/replay/regression/{RUN_OWNED}/{RUN_VICTIM}"
        ).status_code
        == 403
    )


def test_cross_tenant_cancel_does_not_touch_workflow(app, client, temporal_mock):
    evaluations, runs = _victim_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    _override_temporal(app, temporal_mock)
    response = client.post(
        f"/api/v1/runs/{RUN_VICTIM}/cancel", json={"reason": "user_cancelled"}
    )
    assert response.status_code == 403
    temporal_mock.get_workflow_handle.assert_not_called()


def test_same_tenant_cancel_succeeds(app, client, temporal_mock):
    evaluations, runs = _owned_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    _override_temporal(app, temporal_mock)
    response = client.post(
        f"/api/v1/runs/{RUN_OWNED}/cancel", json={"reason": "user_cancelled"}
    )
    assert response.status_code == 200
    temporal_mock.get_workflow_handle.assert_called_once()


def test_cross_tenant_retry_starts_no_provider_workflow(app, client, temporal_mock):
    evaluations, runs = _victim_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    _override_temporal(app, temporal_mock)
    response = client.post(f"/api/v1/runs/{RUN_VICTIM}/retry")
    assert response.status_code == 403
    temporal_mock.start_workflow.assert_not_called()


def test_same_tenant_retry_succeeds(app, client, temporal_mock):
    evaluations = {EVAL_OWNED: _evaluation_row(EVAL_OWNED, project_id=ORG)}
    runs = {
        RUN_OWNED: _run_row(
            RUN_OWNED,
            evaluation_id=EVAL_OWNED,
            status="failed",
            dataset_items=[{"prompt": "owned prompt"}],
        )
    }
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    _override_temporal(app, temporal_mock)
    response = client.post(f"/api/v1/runs/{RUN_OWNED}/retry")
    assert response.status_code == 201
    temporal_mock.start_workflow.assert_called_once()


def test_cross_tenant_log_write_forbidden(app, client):
    evaluations, runs = _victim_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    response = client.post(
        f"/api/v1/runs/{RUN_VICTIM}/logs",
        json={"level": "INFO", "source": "t", "message": "forged"},
    )
    assert response.status_code == 403


def test_same_tenant_log_write_succeeds(app, client):
    evaluations, runs = _owned_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    response = client.post(
        f"/api/v1/runs/{RUN_OWNED}/logs",
        json={"level": "INFO", "source": "t", "message": "hello"},
    )
    assert response.status_code == 201


def test_same_tenant_trace_delete_succeeds(app, client):
    evaluations, runs = _owned_world()
    _override_db(app, membership=_membership_row(), evaluations=evaluations, runs=runs)
    response = client.delete(f"/api/v1/replay/traces/{RUN_OWNED}")
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"


def test_user_without_org_is_forbidden(app, client):
    evaluations, runs = _owned_world()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="user-no-org", org_id=None
    )
    app.dependency_overrides[get_db_session] = lambda: _StubSession(
        membership=_membership_row(), evaluations=evaluations, runs=runs
    )
    assert client.get(f"/api/v1/runs/{RUN_OWNED}").status_code == 403
