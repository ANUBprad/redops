"""Tests that the API and the Temporal worker target the same configured queue.

The single source of truth is ``TemporalConfiguration.task_queue`` which is
derived from ``AppConfig.temporal_task_queue`` (env ``TEMPORAL_TASK_QUEUE``).
Both the worker and the ``POST /api/v1/runs`` submission must resolve to the
same value so evaluation workflows are actually consumed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.router import api_router
from app.core.config import AppConfig
from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.infrastructure.composition.container import InfrastructureContainer
from app.infrastructure.config.temporal import TemporalConfiguration
from app.infrastructure.database.models.tenant import MembershipModel


def _member_session() -> MagicMock:
    """MagicMock session routing membership checks to a real row.

    S-05 requires current-org membership on run creation; the tests'
    other database interactions go through the faked repository.
    """
    session: MagicMock = MagicMock(spec=AsyncSession)
    session.merge = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()

    async def _execute_side_effect(stmt: Any) -> MagicMock:
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        result = MagicMock()
        if "memberships" in sql:
            result.scalar_one_or_none.return_value = MembershipModel(
                id="00000000-0000-0000-0000-0000000000aa",
                user_id="u",
                organization_id="org-queue",
                role="member",
                invited_by="owner",
                is_active=True,
                joined_at=datetime.now(UTC),
            )
        else:
            result.scalar_one_or_none.return_value = None
        return result

    session.execute = AsyncMock(side_effect=_execute_side_effect)
    return session


def _member_user() -> CurrentUser:
    return CurrentUser(user_id="u", org_id="org-queue")


class FakeTemporalClient:
    """Captures workflow submissions for assertions."""

    def __init__(self) -> None:
        self.submissions: list[tuple[object, str]] = []

    async def start_workflow(
        self, workflow: object, args: object, *, id: str, task_queue: str, **kwargs: object
    ) -> None:
        self.submissions.append((workflow, task_queue))


class FakeRunRepository:
    """In-memory stand-in for the evaluation run repository.

    Stores the run produced by the create handler so the queue handler can
    reload it without a real database.
    """

    def __init__(self) -> None:
        self._run = None

    async def save(self, run: object) -> None:
        self._run = run

    async def find_by_id(self, run_id: object) -> object:
        return self._run


@pytest.fixture
def fake_temporal_client():
    return FakeTemporalClient()


def test_worker_configuration_uses_configured_queue() -> None:
    cfg = AppConfig(TEMPORAL_TASK_QUEUE="redops-b1-queue")
    container = InfrastructureContainer(cfg)
    container._register_configurations()
    temporal_config = container.container.resolve(TemporalConfiguration)
    assert temporal_config.task_queue == "redops-b1-queue"


def test_api_submits_run_to_configured_queue(
    fake_temporal_client: FakeTemporalClient,
    monkeypatch,
) -> None:
    cfg = AppConfig(
        TEMPORAL_TASK_QUEUE="redops-b1-queue",
        OPENAI_API_KEY="sk-test",
        ANTHROPIC_API_KEY="sk-test-ant",
    )
    monkeypatch.setattr("app.core.dependencies.get_config", lambda: cfg)
    fake_repo = FakeRunRepository()
    monkeypatch.setattr("app.api.evaluation_run._get_repository", lambda s: fake_repo)

    app = FastAPI()
    app.include_router(api_router)
    session = _member_session()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: _member_user()
    app.dependency_overrides[get_temporal_client] = lambda: fake_temporal_client

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runs",
            json={
                "evaluation_name": "B1 queue check",
                "provider": "openai",
                "model": "gpt-4o",
                "metrics": ["latency"],
                "dataset_items": [{"prompt": "hello"}],
            },
        )

    assert response.status_code == 201, response.text
    assert fake_temporal_client.submissions, "start_workflow was never called"
    _, task_queue = fake_temporal_client.submissions[0]
    assert task_queue == "redops-b1-queue"


def test_api_and_worker_share_configured_queue(
    fake_temporal_client: FakeTemporalClient,
    monkeypatch,
) -> None:
    cfg = AppConfig(
        TEMPORAL_TASK_QUEUE="redops-b1-queue",
        OPENAI_API_KEY="sk-test",
        ANTHROPIC_API_KEY="sk-test-ant",
    )
    monkeypatch.setattr("app.core.dependencies.get_config", lambda: cfg)

    worker_container = InfrastructureContainer(cfg)
    worker_container._register_configurations()
    worker_queue = worker_container.container.resolve(TemporalConfiguration).task_queue

    fake_repo = FakeRunRepository()
    monkeypatch.setattr("app.api.evaluation_run._get_repository", lambda s: fake_repo)

    app = FastAPI()
    app.include_router(api_router)
    session = _member_session()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: _member_user()
    app.dependency_overrides[get_temporal_client] = lambda: fake_temporal_client

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/runs",
            json={
                "evaluation_name": "B1 shared queue",
                "provider": "openai",
                "model": "gpt-4o",
                "metrics": ["latency"],
                "dataset_items": [{"prompt": "hello"}],
            },
        )

    assert response.status_code == 201, response.text
    _, api_queue = fake_temporal_client.submissions[0]
    assert api_queue == worker_queue == "redops-b1-queue"
