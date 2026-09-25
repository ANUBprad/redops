"""Regression tests: analytics tenant isolation (S-06).

Forensic audit showed all 12 ``/analytics`` endpoints auth-only while
every analytics service aggregates GLOBALLY: ``project_id`` is accepted
but never honored (dashboard/cost/latency/trends/leaderboard/comparison/
safety all ignore it), run/metric/attack repositories are queried without
any tenant constraint, and aggregates (totals, averages, breakdowns,
distributions, report contents) mix every organization's rows. Caller
filters (run_id/evaluation_id/project_id) are trusted raw identifiers.

The fix reuses the established tenancy semantics only:
  - every analytics route requires current-org membership and scopes by
    the JWT org (caller-supplied project_id is ignored);
  - run-keyed metric reads (distribution/pass-fail) and report/export
    run_id/evaluation_id filters are gated via require_owned_run /
    require_owned_evaluation BEFORE any computation or Temporal work;
  - repository row-sets are scoped before Python aggregation:
    RunQuery.owner_project_id (S-05), owner support in run/metric/attack
    ``find_by_date_range``, AttackRunQuery.owner_project_id (attack runs
    join to owned evaluation runs), evaluation count via scoped list;
  - export carries the owner into the Temporal input so the worker
    generates with the requester's scope, not the caller filter.

Two-organization fixture with deliberately distinguishable values makes
any cross-tenant contribution obvious. The stub emulates scoped vs
unscoped SQL (JOIN present -> in-scope rows only), proving the tenant
constraint reaches the query; real-SQLite tests prove the new
predicates execute correctly. Experiment-comparison's run path is dead
(EvaluationRun has no experiment_id) — covered as a STALE classification
proof, not a fix (experiment ownership itself is a later lead).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.dependencies import (
    CurrentUser,
    get_current_user,
    get_db_session,
    get_temporal_client,
)
from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.infrastructure.database.models.attack_run import AttackRunModel
from app.infrastructure.database.models.evaluation import EvaluationModel
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.experiment import ExperimentModel
from app.infrastructure.database.models.metric_result import MetricResultModel
from app.infrastructure.database.models.tenant import MembershipModel
from app.infrastructure.database.repositories.attack_run_repository import (
    SqlAlchemyAttackRunRepository,
)
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
)
from app.infrastructure.database.repositories.metric_result_repository import (
    SqlAlchemyMetricResultRepository,
)
from app.redteam.domain.enums import AttackStatus

ORG = "org-acme"
OTHER_ORG = "org-rival"
EVAL_A = "00000000-0000-0000-0000-0000000000a1"
EVAL_B = "00000000-0000-0000-0000-0000000000a2"
RUN_A1 = "00000000-0000-0000-0000-0000000000b1"
RUN_A2_ORPHAN = "00000000-0000-0000-0000-0000000000b2"
RUN_B1 = "00000000-0000-0000-0000-0000000000b3"
RUN_B2_ORPHAN = "00000000-0000-0000-0000-0000000000b4"
ATK_A = "00000000-0000-0000-0000-0000000000c1"
ATK_B = "00000000-0000-0000-0000-0000000000c2"
EXP_A = "00000000-0000-0000-0000-0000000000d1"
USER = CurrentUser(user_id="user-analyst", org_id=ORG)

NOW = datetime.now(UTC)


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
    """Routes SQL to fixture rows; scoped SQL (JOIN) yields in-scope rows."""

    def __init__(self, *, membership=None, evaluations=None, runs=None,
                 metrics=None, attacks=None, experiments=None):
        self._membership = membership
        self._evaluations = evaluations or {}
        self._runs = runs or {}
        self._metrics = metrics or []
        self._attacks = attacks or {}
        self._experiments = experiments or {}

    @staticmethod
    def _which(sql: str, mapping: dict):
        for key, row in mapping.items():
            if key.lower() in sql:
                return row
        return None

    def _run_in_scope(self, row: EvaluationRunModel) -> bool:
        if row.evaluation_id:
            evaluation = self._evaluations.get(row.evaluation_id)
            return evaluation is not None and evaluation.project_id == ORG
        return (row.metadata_ or {}).get("project_id") == ORG

    def _scoped_runs(self, sql: str) -> list:
        rows = [r for r in self._runs.values() if self._run_in_scope(r)]
        for column, attr in (
            ("evaluation_runs.evaluation_id", "evaluation_id"),
            ("evaluation_runs.status", "status"),
            ("evaluation_runs.provider", "provider"),
            ("evaluation_runs.model", "model"),
        ):
            value = _literal(sql, column)
            if value is not None:
                rows = [r for r in rows if str(getattr(r, attr) or "") == value]
        limit = re.search(r"limit (\d+)", sql)
        offset = re.search(r"offset (\d+)", sql)
        if limit is not None:
            start = int(offset.group(1)) if offset else 0
            rows = rows[start : start + int(limit.group(1))]
        return rows

    def _scoped_metrics(self) -> list:
        owned_run_ids = {rid for rid, r in self._runs.items() if self._run_in_scope(r)}
        return [m for m in self._metrics if m.run_id in owned_run_ids]

    def _scoped_attacks(self) -> list:
        owned_run_ids = {rid for rid, r in self._runs.items() if self._run_in_scope(r)}
        return [a for a in self._attacks.values() if a.evaluation_run_id in owned_run_ids]

    async def execute(self, stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        if "memberships" in sql:
            return _StubResult(self._membership)
        if "experiments" in sql:
            return _StubResult(self._which(sql, self._experiments))
        if "metric_results" in sql:
            if "join" in sql:
                return _StubResult(self._scoped_metrics())
            run_id = _literal(sql, "metric_results.run_id")
            if run_id is not None:
                return _StubResult([m for m in self._metrics if m.run_id == run_id])
            return _StubResult(list(self._metrics))
        if "attack_runs" in sql:
            if "join" in sql:
                return _StubResult(self._scoped_attacks())
            if "count(" in sql:
                return _StubResult(None, count=len(self._attacks))
            return _StubResult(list(self._attacks.values()))
        if "evaluation_runs" in sql:
            if "count(" in sql:
                if "join" in sql:
                    return _StubResult(None, count=len(self._scoped_runs(sql)))
                return _StubResult(None, count=len(self._runs))
            if "limit" in sql or "created_at >=" in sql:
                if "join" in sql:
                    return _StubResult(self._scoped_runs(sql))
                return _StubResult(list(self._runs.values()))
            return _StubResult(self._which(sql, self._runs))
        if "evaluations" in sql:
            project = _literal(sql, "evaluations.project_id")
            rows = list(self._evaluations.values())
            if project is not None:
                rows = [r for r in rows if r.project_id == project]
            if "count(" in sql:
                return _StubResult(None, count=len(rows))
            if "limit" in sql:
                return _StubResult(rows)
            return _StubResult(self._which(sql, self._evaluations))
        return _StubResult(None)

    def add(self, _model):
        pass

    async def merge(self, _model):
        pass

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


def _run_row(
    run_id: str,
    *,
    evaluation_id: str | None,
    project_id: str | None = None,
    provider: str = "openai",
    model: str = "gpt-4o",
    cost: float = 0.0,
    latency: int = 0,
    tokens: int = 0,
    status: str = "completed",
) -> EvaluationRunModel:
    return EvaluationRunModel(
        id=run_id,
        evaluation_id=evaluation_id,
        evaluation_name="eval",
        workflow_id=None,
        provider=provider,
        model=model,
        status=status,
        priority="normal",
        items_total=2,
        items_completed=2,
        items_failed=0,
        token_input=tokens // 2,
        token_output=tokens - tokens // 2,
        cost=cost,
        average_latency_ms=latency,
        failure_reason=None,
        config={
            "name": "eval",
            "eval_type": "single",
            "profile": {"provider_name": provider, "model_id": model},
            "metrics": ["accuracy"],
            "budget": {},
            "limits": {},
            "policy": {},
            "priority": "normal",
            "dataset_items": [],
        },
        profile={"provider_name": provider, "model_id": model},
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


def _metric_row(
    row_id: int, run_id: str, *, score: float, error: str | None = None
) -> MetricResultModel:
    return MetricResultModel(
        id=row_id,
        run_id=run_id,
        item_id=f"item-{row_id}",
        metric_name="accuracy",
        score=score,
        normalized_score=score,
        raw_output="",
        reasoning="",
        metadata_json={"run_id": run_id, "item_id": f"item-{row_id}"},
        execution_time_ms=5,
        error=error,
        created_at=NOW,
        confidence=0.9,
        version="1.0.0",
        cost_usd=0.0,
    )


def _attack_row(
    attack_id: str, run_id: str | None, *, total: int, violated: int
) -> AttackRunModel:
    return AttackRunModel(
        id=attack_id,
        evaluation_run_id=run_id,
        status=AttackStatus.COMPLETED.value,
        attack_definition_ids=[],
        configuration={},
        items_total=total,
        items_completed=total,
        items_passed=total - violated,
        items_violated=violated,
        items_failed=0,
        campaign_results=None,
        version=1,
        started_at=NOW,
        completed_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _experiment_row() -> ExperimentModel:
    return ExperimentModel(
        id=EXP_A,
        project_id=ORG,
        name="owned-experiment",
        description=None,
        hypothesis=None,
        status=ExperimentStatus.ACTIVE.value,
        baseline_run_id=None,
        conclusion=None,
        tags=[],
        created_by=USER.user_id,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _world() -> tuple[dict, dict, list, dict, dict]:
    evaluations = {
        EVAL_A: _evaluation_row(EVAL_A, project_id=ORG),
        EVAL_B: _evaluation_row(EVAL_B, project_id=OTHER_ORG),
    }
    runs = {
        RUN_A1: _run_row(
            RUN_A1, evaluation_id=EVAL_A, provider="openai", model="gpt-4o",
            cost=10.0, latency=100, tokens=150,
        ),
        RUN_A2_ORPHAN: _run_row(
            RUN_A2_ORPHAN, evaluation_id=None, project_id=ORG,
            provider="openai", model="gpt-4o-mini", cost=5.0, latency=200, tokens=60,
        ),
        RUN_B1: _run_row(
            RUN_B1, evaluation_id=EVAL_B, provider="anthropic", model="claude-3",
            cost=100.0, latency=1000, tokens=1500,
        ),
        RUN_B2_ORPHAN: _run_row(
            RUN_B2_ORPHAN, evaluation_id=None, project_id=OTHER_ORG,
            provider="anthropic", model="claude-3", cost=50.0, latency=2000,
            tokens=600, status="failed",
        ),
    }
    metrics = [
        _metric_row(1, RUN_A1, score=0.9),
        _metric_row(2, RUN_A1, score=0.9),
        _metric_row(3, RUN_B1, score=0.1),
    ]
    attacks = {
        ATK_A: _attack_row(ATK_A, RUN_A1, total=10, violated=1),
        ATK_B: _attack_row(ATK_B, RUN_B1, total=20, violated=10),
    }
    return evaluations, runs, metrics, attacks, {"exp": _experiment_row()}


def _override_db(app, *, membership=None) -> None:
    evaluations, runs, metrics, attacks, experiments = _world()
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db_session] = lambda: _StubSession(
        membership=membership,
        evaluations=evaluations,
        runs=runs,
        metrics=metrics,
        attacks=attacks,
        experiments=experiments,
    )


@pytest.fixture
def temporal_mock():
    client = MagicMock()
    client.start_workflow = AsyncMock()
    return client


ROUTES_401 = [
    ("get", "/api/v1/analytics/dashboard", None),
    ("get", "/api/v1/analytics/trends", None),
    ("get", "/api/v1/analytics/cost", None),
    ("get", "/api/v1/analytics/latency", None),
    ("get", "/api/v1/analytics/safety", None),
    ("get", "/api/v1/analytics/leaderboard", None),
    ("get", "/api/v1/analytics/comparison", None),
    ("get", "/api/v1/analytics/reports/generate", None),
    ("get", "/api/v1/analytics/experiment-comparison", {"experiment_id": EXP_A}),
    ("get", "/api/v1/analytics/metric-distribution", None),
    ("get", "/api/v1/analytics/pass-fail-summary", {"run_id": RUN_A1}),
    ("post", "/api/v1/analytics/export", None),
]


def _request(client, method, path, params):
    if method == "get":
        return client.get(path, params=params or {})
    return client.post(path, params=params or {})


@pytest.mark.parametrize(("method", "path", "params"), ROUTES_401)
def test_unauthenticated_rejected(client, method, path, params):
    assert _request(client, method, path, params).status_code == 401


@pytest.mark.parametrize(("method", "path", "params"), ROUTES_401)
def test_non_member_forbidden(app, client, method, path, params):
    _override_db(app, membership=None)
    assert _request(client, method, path, params).status_code == 403


def test_dashboard_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/analytics/dashboard").json()
    assert payload["total_evaluations"] == 1
    assert payload["completed_runs"] == 2
    assert payload["average_cost"] == 7.5
    assert payload["total_token_usage"] == 210
    assert payload["attack_success_rate"] == 10.0
    assert payload["average_safety_score"] == 90.0
    activity_ids = {entry["id"] for entry in payload["recent_activity"]}
    assert activity_ids.isdisjoint({RUN_B1, RUN_B2_ORPHAN, ATK_B})


def test_dashboard_ignores_foreign_project_filter(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get(
        "/api/v1/analytics/dashboard", params={"project_id": OTHER_ORG}
    ).json()
    assert payload["total_evaluations"] == 1
    assert payload["average_cost"] == 7.5


def test_cost_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/analytics/cost").json()
    assert payload["total_cost"] == 15.0
    providers = {p["provider"] for p in payload["cost_by_provider"]}
    assert providers == {"openai"}
    models = {m["model"]: m["total_cost"] for m in payload["cost_by_model"]}
    assert models == {"gpt-4o": 10.0, "gpt-4o-mini": 5.0}


def test_latency_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/analytics/latency").json()
    assert payload["average_latency_ms"] == 150.0
    assert payload["max_latency_ms"] == 200
    providers = {p["provider"] for p in payload["latency_by_provider"]}
    assert providers == {"openai"}


def test_trends_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get(
        "/api/v1/analytics/trends", params={"metric_name": "accuracy"}
    ).json()
    assert payload["points"] != []
    assert all(point["value"] == 0.9 for point in payload["points"])


def test_leaderboard_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/analytics/leaderboard").json()
    names = {entry["entity_id"] for entry in payload["entries"]}
    assert names == {"gpt-4o", "gpt-4o-mini"}


def test_leaderboard_foreign_model_filter_is_empty(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get(
        "/api/v1/analytics/comparison",
        params={"entity_type": "model", "entity_ids": "claude-3"},
    ).json()
    assert payload["compared_items"] == []


def test_comparison_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/analytics/comparison").json()
    names = {item["entity_id"] for item in payload["compared_items"]}
    assert names == {"gpt-4o", "gpt-4o-mini"}


def test_safety_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/analytics/safety").json()
    assert payload["total_attacks"] == 10
    assert payload["total_violations"] == 1


def test_distribution_foreign_run_denied(app, client):
    _override_db(app, membership=_membership_row())
    response = client.get(
        "/api/v1/analytics/metric-distribution", params={"run_id": RUN_B1}
    )
    assert response.status_code == 403


def test_distribution_own_run(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get(
        "/api/v1/analytics/metric-distribution", params={"run_id": RUN_A1}
    ).json()
    assert payload["total"] == 2


def test_pass_fail_foreign_run_denied(app, client):
    _override_db(app, membership=_membership_row())
    response = client.get(
        "/api/v1/analytics/pass-fail-summary", params={"run_id": RUN_B1}
    )
    assert response.status_code == 403


def test_pass_fail_own_run(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get(
        "/api/v1/analytics/pass-fail-summary", params={"run_id": RUN_A1}
    ).json()
    assert payload["run_id"] == RUN_A1
    assert "accuracy" in payload["metrics"]


def test_report_executive_scoped_to_org(app, client):
    _override_db(app, membership=_membership_row())
    payload = client.get("/api/v1/analytics/reports/generate").json()
    assert payload["statistics"]["total_evaluations"] == 1.0
    assert payload["statistics"]["total_cost"] == 15.0


def test_report_foreign_run_denied(app, client):
    _override_db(app, membership=_membership_row())
    response = client.get(
        "/api/v1/analytics/reports/generate",
        params={"report_type": "run_report", "run_id": RUN_B1},
    )
    assert response.status_code == 403


def test_report_foreign_evaluation_denied(app, client):
    _override_db(app, membership=_membership_row())
    response = client.get(
        "/api/v1/analytics/reports/generate",
        params={"report_type": "evaluation_report", "evaluation_id": EVAL_B},
    )
    assert response.status_code == 403


def test_export_non_member_denied_no_workflow(app, client, temporal_mock):
    _override_db(app, membership=None)
    app.dependency_overrides[get_temporal_client] = lambda: temporal_mock
    assert client.post("/api/v1/analytics/export").status_code == 403
    temporal_mock.start_workflow.assert_not_called()


def test_export_foreign_run_denied_no_workflow(app, client, temporal_mock):
    _override_db(app, membership=_membership_row())
    app.dependency_overrides[get_temporal_client] = lambda: temporal_mock
    response = client.post("/api/v1/analytics/export", params={"run_id": RUN_B1})
    assert response.status_code == 403
    temporal_mock.start_workflow.assert_not_called()


def test_export_carries_caller_org(app, client, temporal_mock):
    _override_db(app, membership=_membership_row())
    app.dependency_overrides[get_temporal_client] = lambda: temporal_mock
    response = client.post(
        "/api/v1/analytics/export", params={"project_id": OTHER_ORG}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "started"
    temporal_mock.start_workflow.assert_called_once()
    sent_input = temporal_mock.start_workflow.call_args[0][1]
    assert getattr(sent_input, "owner_project_id", "") == ORG


def test_experiment_comparison_run_path_is_dead(app, client):
    """EvaluationRun has no experiment_id, so no run data can leak here.

    The endpoint can only echo the experiment title / empty summary;
    experiment ownership itself is a separate later lead.
    """
    _override_db(app, membership=_membership_row())
    payload = client.get(
        "/api/v1/analytics/experiment-comparison", params={"experiment_id": EXP_A}
    ).json()
    assert payload["compared_items"] == []
    assert "No runs found" in payload["summary"]


class TestAnalyticsTenantPredicates:
    """New repository predicates execute correctly on real SQLite."""

    @pytest.fixture
    async def sqlite_repos(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from app.infrastructure.database.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    EvaluationModel.__table__,
                    EvaluationRunModel.__table__,
                    MetricResultModel.__table__,
                    AttackRunModel.__table__,
                ],
            )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            evaluations, runs, metrics, attacks, _ = _world()
            session.add_all(evaluations.values())
            session.add_all(runs.values())
            session.add_all(metrics)
            session.add_all(attacks.values())
            await session.commit()
            yield (
                SqlAlchemyEvaluationRunRepository(session),
                SqlAlchemyMetricResultRepository(session),
                SqlAlchemyAttackRunRepository(session),
            )
        await engine.dispose()

    async def test_run_date_range_scoped(self, sqlite_repos):
        run_repo, _, _ = sqlite_repos
        rows = await run_repo.find_by_date_range(
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            owner_project_id=ORG,
        )
        assert {str(r.id) for r in rows} == {RUN_A1, RUN_A2_ORPHAN}

    async def test_run_date_range_unscoped_without_owner(self, sqlite_repos):
        run_repo, _, _ = sqlite_repos
        rows = await run_repo.find_by_date_range(
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
        )
        assert len(rows) == 4

    async def test_metric_date_range_scoped(self, sqlite_repos):
        _, metric_repo, _ = sqlite_repos
        rows = await metric_repo.find_by_date_range(
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            owner_project_id=ORG,
        )
        assert {r.metadata["run_id"] for r in rows} == {RUN_A1}
        assert all(r.score == 0.9 for r in rows)

    async def test_attack_list_and_date_range_scoped(self, sqlite_repos):
        from app.redteam.contracts.repositories import AttackRunQuery

        _, _, attack_repo = sqlite_repos
        paged = await attack_repo.list(AttackRunQuery(owner_project_id=ORG))
        assert [str(a.id) for a in paged.items] == [ATK_A]
        assert paged.total == 1
        ranged = await attack_repo.find_by_date_range(
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime(2100, 1, 1, tzinfo=UTC),
            owner_project_id=ORG,
        )
        assert [str(a.id) for a in ranged] == [ATK_A]
