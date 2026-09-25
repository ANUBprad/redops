"""API-level lifecycle tests for red team runs.

Proves the production endpoint contract for start/cancel:

- F2  start commits RUNNING first, then schedules the Temporal workflow on
      the configured queue; a scheduling failure marks the run FAILED and
      returns 502 (never a misleading RUNNING).
- F1  cancel always signals the workflow handle after committing CANCELLED;
      a NOT_FOUND handle is benign, any other Temporal error is a 502.
- domain guards: duplicate/terminal starts and terminal cancels are 409s.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.service import RPCError, RPCStatusCode

from app.api.router import api_router
from app.core.config import AppConfig
from app.core.dependencies import (
    CurrentUser,
    get_config_dependency,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.redteam.domain.entities import AttackRun
from app.redteam.domain.enums import AttackStatus
from app.redteam.domain.value_objects import AttackConfiguration
from app.redteam.temporal.activities import RedTeamWorkflowInput

MOCK_ID = "9f8d2a1e-0000-4000-8000-000000000001"


class _FakeHandle:
    def __init__(self) -> None:
        self.signals: list[str] = []
        self.signal_error: Exception | None = None

    async def signal(self, name: str) -> None:
        if self.signal_error is not None:
            raise self.signal_error
        self.signals.append(name)


class FakeTemporalClient:
    """Records workflow submissions and cancel signals; injectable failures."""

    def __init__(self) -> None:
        self.submissions: list[tuple[object, RedTeamWorkflowInput, str, str]] = []
        self.handles: dict[str, _FakeHandle] = {}
        self.start_error: Exception | None = None

    async def start_workflow(
        self, workflow: object, input: object, *, id: str, task_queue: str, **kwargs: object
    ) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.submissions.append((workflow, input, id, task_queue))
        self.handles.setdefault(id, _FakeHandle())

    def get_workflow_handle(self, workflow_id: str) -> _FakeHandle:
        return self.handles.setdefault(workflow_id, _FakeHandle())


class FakeRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, AttackRun] = {}

    def seed(self, run: AttackRun) -> None:
        self._runs[str(run.id)] = run

    async def find_by_id(self, run_id: Any) -> AttackRun | None:
        return self._runs.get(str(run_id))

    async def save(self, run: AttackRun) -> None:
        self._runs[str(run.id)] = run


def _run(*, status: AttackStatus) -> AttackRun:
    run = AttackRun.create(
        evaluation_run_id=None,
        configuration=AttackConfiguration(
            target_provider="test-provider",
            target_model="m",
        ),
    )
    if status == AttackStatus.QUEUED:
        run.queue()
    elif status == AttackStatus.RUNNING:
        run.queue()
        run.start(total_items=3)
    elif status == AttackStatus.COMPLETED:
        run.queue()
        run.start(total_items=3)
        run.complete()
    elif status == AttackStatus.FAILED:
        run.queue()
        run.start(total_items=3)
        run.fail("gone")
    elif status == AttackStatus.CANCELLED:
        run.queue()
        run.start(total_items=3)
        run.cancel()
    return run


@pytest.fixture
def fake_temporal_client() -> FakeTemporalClient:
    return FakeTemporalClient()


def _make_app(
    fake_temporal_client: FakeTemporalClient, repo: FakeRunRepository
) -> tuple[FastAPI, Any]:
    cfg = AppConfig(
        TEMPORAL_TASK_QUEUE="redops-b1-queue",
        OPENAI_API_KEY="sk-test",
        ANTHROPIC_API_KEY="sk-test-ant",
    )

    app = FastAPI()
    app.include_router(api_router)
    session: Any = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock(spec=AsyncSession)
    session.commit = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id="u")
    app.dependency_overrides[get_temporal_client] = lambda: fake_temporal_client
    # get_config_dependency() resolves the configured task queue.
    app.dependency_overrides[get_config_dependency] = lambda: cfg
    return app, session


@pytest.mark.parametrize("status", [AttackStatus.CREATED, AttackStatus.QUEUED])
def test_start_schedules_workflow_and_commits(
    fake_temporal_client: FakeTemporalClient, monkeypatch, status: AttackStatus
) -> None:
    repo = FakeRunRepository()
    repo.seed(_run(status=status))
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, session = _make_app(fake_temporal_client, repo)

    run_id = next(iter(repo._runs))
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/redteam/runs/{run_id}/start",
            json={"total_items": 3},
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "running"
    assert len(fake_temporal_client.submissions) == 1
    _, wf_input, workflow_id, task_queue = fake_temporal_client.submissions[0]
    assert isinstance(wf_input, RedTeamWorkflowInput)
    assert wf_input.attack_run_id == run_id
    assert workflow_id == f"red-team-run-{run_id}"
    assert task_queue == "redops-b1-queue"
    session.commit.assert_awaited()


def test_start_twice_conflicts_and_never_reschedules(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.RUNNING)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/redteam/runs/{run.id}/start",
            json={"total_items": 3},
        )

    assert response.status_code == 409, response.text
    assert fake_temporal_client.submissions == []


def test_start_terminal_run_conflicts(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.COMPLETED)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/start", json={"total_items": 1})

    assert response.status_code == 409, response.text
    assert fake_temporal_client.submissions == []


def test_start_unknown_run_returns_404(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/redteam/runs/{MOCK_ID}/start",
            json={"total_items": 1},
        )

    assert response.status_code == 404, response.text
    assert fake_temporal_client.submissions == []


def test_start_scheduling_failure_marks_run_failed_and_returns_502(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.CREATED)
    repo.seed(run)
    fake_temporal_client.start_error = RuntimeError("temporal down")
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, session = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/start", json={"total_items": 1})

    assert response.status_code == 502, response.text
    saved = repo._runs[str(run.id)]
    assert saved.status == AttackStatus.FAILED
    session.commit.assert_awaited()


def test_cancel_running_run_signals_workflow(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.RUNNING)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)
    workflow_id = f"red-team-run-{run.id}"
    fake_temporal_client.get_workflow_handle(workflow_id)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert fake_temporal_client.handles[workflow_id].signals == ["cancel"]
    assert repo._runs[str(run.id)].status == AttackStatus.CANCELLED


def test_cancel_already_cancelled_is_idempotent_and_signals(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.CANCELLED)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)
    workflow_id = f"red-team-run-{run.id}"

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/cancel")

    assert response.status_code == 200, response.text
    assert fake_temporal_client.handles[workflow_id].signals == ["cancel"]
    assert repo._runs[str(run.id)].status == AttackStatus.CANCELLED


def test_cancel_missing_handle_is_benign_noop(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.RUNNING)
    repo.seed(run)
    fake_temporal_client.get_workflow_handle(f"red-team-run-{run.id}").signal_error = RPCError(
        "workflow not found for ID: red-team-run-x",
        RPCStatusCode.NOT_FOUND,
        b"",
    )
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/cancel")

    assert response.status_code == 200, response.text
    assert repo._runs[str(run.id)].status == AttackStatus.CANCELLED


def test_cancel_temporal_unavailable_returns_502_but_keeps_cancelled(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.RUNNING)
    repo.seed(run)
    fake_temporal_client.get_workflow_handle(f"red-team-run-{run.id}").signal_error = RPCError(
        "temporal unavailable", RPCStatusCode.UNAVAILABLE, b""
    )
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/cancel")

    assert response.status_code == 502, response.text
    # The committed CANCELLED state is not reverted by the signal failure.
    assert repo._runs[str(run.id)].status == AttackStatus.CANCELLED


def test_cancel_terminal_run_conflicts_without_signal(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.COMPLETED)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)
    workflow_id = f"red-team-run-{run.id}"

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/cancel")

    assert response.status_code == 409, response.text
    assert fake_temporal_client.get_workflow_handle(workflow_id).signals == []
    assert repo._runs[str(run.id)].status == AttackStatus.COMPLETED


# -----------------------------------------------------------------------
# Additional coverage
# -----------------------------------------------------------------------


def test_start_forwards_config_target_fields_in_workflow_input(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.CREATED)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/start", json={"total_items": 1})

    assert response.status_code == 200, response.text
    _, wf_input, *_ = fake_temporal_client.submissions[0]
    assert wf_input.target_provider == "test-provider"
    assert wf_input.target_model == "m"


def test_start_failure_message_mentions_workflow_scheduling_error(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.CREATED)
    repo.seed(run)
    fake_temporal_client.start_error = RuntimeError("connection refused")
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/start", json={"total_items": 1})

    assert response.status_code == 502
    assert "Failed to schedule red team workflow" in response.json()["detail"]


@pytest.mark.parametrize("status", [AttackStatus.CREATED, AttackStatus.QUEUED])
def test_cancel_queued_and_created_runs_signal_workflow(
    fake_temporal_client: FakeTemporalClient, monkeypatch, status: AttackStatus
) -> None:
    repo = FakeRunRepository()
    run = _run(status=status)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)
    workflow_id = f"red-team-run-{run.id}"

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert fake_temporal_client.handles[workflow_id].signals == ["cancel"]
    assert repo._runs[str(run.id)].status == AttackStatus.CANCELLED


def test_cancel_unknown_run_returns_404_no_signal(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{MOCK_ID}/cancel")

    assert response.status_code == 404, response.text
    assert fake_temporal_client.handles == {}


def test_cancel_failed_run_conflicts(fake_temporal_client: FakeTemporalClient, monkeypatch) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.FAILED)
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.post(f"/api/v1/redteam/runs/{run.id}/cancel")

    assert response.status_code == 409, response.text
    assert repo._runs[str(run.id)].status == AttackStatus.FAILED


def test_get_run_returns_persisted_campaign_results(
    fake_temporal_client: FakeTemporalClient, monkeypatch
) -> None:
    repo = FakeRunRepository()
    run = _run(status=AttackStatus.COMPLETED)
    run.record_campaign_results({"state": "completed", "rounds": [{"round_number": 0}]})
    repo.seed(run)
    monkeypatch.setattr("app.api.redteam._get_run_repo", lambda s: repo)
    app, _ = _make_app(fake_temporal_client, repo)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/redteam/runs/{run.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["campaign_results"]["state"] == "completed"
    assert body["campaign_results"]["rounds"] == [{"round_number": 0}]
