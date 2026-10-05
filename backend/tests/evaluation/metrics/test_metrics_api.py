"""Integration tests for metrics API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.metrics import metrics_router
from app.core.dependencies import CurrentUser, get_current_user, get_db_session
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.models.tenant import MembershipModel

RUN_ID = "00000000-0000-0000-0000-000000000001"
TENANT_ORG_ID = "org-acme"


@pytest.fixture
def mock_session(
    mock_membership: MembershipModel,
    mock_run: EvaluationRunModel,
) -> MagicMock:
    """Create a mock async session for testing."""
    session = MagicMock(spec=AsyncSession)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar.return_value = 0
    mock_result.scalar_one_or_none.return_value = None

    def execute_side_effect(stmt, parameters=None) -> MagicMock:
        """Route stub queries to the tenant-owned rows; everything else empty.

        Mirrors the production ``AsyncSession.execute(stmt, parameters)``
        arity: the metric-result upsert passes an executemany parameter list
        as the second positional argument, so the double must accept it.
        """
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).lower()
        if "memberships" in sql:
            membership_result = MagicMock()
            membership_result.scalar_one_or_none.return_value = mock_membership
            return membership_result
        if "evaluation_runs" in sql and RUN_ID in sql:
            run_result = MagicMock()
            run_result.scalar_one_or_none.return_value = mock_run
            return run_result
        return mock_result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add_all = MagicMock()

    return session


@pytest.fixture
def mock_membership() -> MembershipModel:
    """Create an active membership row for the test user."""
    return MembershipModel(
        id="00000000-0000-0000-0000-0000000000aa",
        user_id="test-user",
        organization_id=TENANT_ORG_ID,
        role="member",
        is_active=True,
    )


@pytest.fixture
def mock_run() -> EvaluationRunModel:
    """Create the run the run-keyed endpoints resolve.

    Deliberately parentless (``evaluation_id=None``) so ownership is carried
    by the persisted ``metadata.project_id`` - the fallback
    ``require_owned_run`` uses for runs without a parent evaluation. The
    membership row above plus that org match are both still enforced, so a
    cross-tenant caller still gets 403.
    """
    now = datetime.now(UTC)
    return EvaluationRunModel(
        id=RUN_ID,
        evaluation_id=None,
        evaluation_name="metrics-api-run",
        provider="openai",
        model="gpt-4o",
        status="completed",
        priority="normal",
        items_total=0,
        items_completed=0,
        items_failed=0,
        token_input=0,
        token_output=0,
        cost=0.0,
        average_latency_ms=0,
        config={"name": "metrics-api-run", "metrics": ["accuracy"]},
        profile={"provider_name": "openai", "model_id": "gpt-4o"},
        metadata_={"project_id": TENANT_ORG_ID, "created_by": "test-user"},
        version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_app(mock_session: MagicMock) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(metrics_router)
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id="test-user",
        org_id=TENANT_ORG_ID,
    )
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create a test client."""
    with TestClient(test_app) as c:
        yield c


class TestListMetrics:
    """Tests for GET /metrics."""

    def test_list_all_metrics(self, client: TestClient) -> None:
        """List all available metrics."""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        names = {m["name"] for m in data}
        assert "answer_relevance" in names
        assert "correctness" in names
        assert "groundedness" in names
        assert "hallucination" in names
        assert "faithfulness" in names
        assert "latency" in names
        assert "token_usage" in names
        assert "cost" in names
        assert "json_validity" in names
        assert "tool_call_correctness" in names

    def test_filter_by_category(self, client: TestClient) -> None:
        """Filter metrics by category."""
        response = client.get("/metrics?category=quality")
        assert response.status_code == 200
        data = response.json()
        assert all(m["category"] == "quality" for m in data)

    def test_filter_by_performance_category(self, client: TestClient) -> None:
        """Filter metrics by performance category."""
        response = client.get("/metrics?category=performance")
        assert response.status_code == 200
        data = response.json()
        assert all(m["category"] == "performance" for m in data)

    def test_invalid_category(self, client: TestClient) -> None:
        """Invalid category returns 422."""
        response = client.get("/metrics?category=invalid")
        assert response.status_code == 422
        detail = response.json()
        assert "detail" in detail

    def test_metric_response_shape(self, client: TestClient) -> None:
        """Each metric definition has the expected fields."""
        response = client.get("/metrics")
        data = response.json()
        for metric in data:
            assert "name" in metric
            assert "display_name" in metric
            assert "description" in metric
            assert "category" in metric
            assert "scale" in metric
            assert "version" in metric


class TestScoreItem:
    """Tests for POST /metrics/score."""

    def test_score_with_default_metrics(
        self,
        client: TestClient,
        mock_session: MagicMock,
    ) -> None:
        """Score with default (all) metrics."""
        response = client.post(
            "/metrics/score",
            json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "item_id": "00000000-0000-0000-0000-000000000002",
                "prompt": "What is Python?",
                "response": "Python is a programming language.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_score_with_specific_metrics(
        self,
        client: TestClient,
    ) -> None:
        """Score with specific metrics only."""
        response = client.post(
            "/metrics/score",
            json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "item_id": "00000000-0000-0000-0000-000000000002",
                "prompt": "test",
                "response": "test response",
                "metric_names": ["answer_relevance", "correctness"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {r["metric_name"] for r in data}
        assert names == {"answer_relevance", "correctness"}

    def test_score_response_shape(self, client: TestClient) -> None:
        """Each metric result has the expected fields."""
        response = client.post(
            "/metrics/score",
            json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "item_id": "00000000-0000-0000-0000-000000000002",
                "prompt": "test",
                "response": "test response",
                "metric_names": ["json_validity"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        result = data[0]
        assert "metric_name" in result
        assert "score" in result
        assert "normalized_score" in result
        assert "raw_output" in result
        assert "reasoning" in result
        assert "metadata" in result
        assert "execution_time_ms" in result
        assert "error" in result or result["error"] is None

    def test_score_preserves_cost_usd_from_metadata(self, client: TestClient) -> None:
        """cost metric surfaces the real cost_usd through the response.

        Regression: the sync score path previously dropped cost_usd (and
        confidence/version) when building the HTTP response, returning
        defaults instead of the values produced during evaluation.
        """
        response = client.post(
            "/metrics/score",
            json={
                "run_id": "00000000-0000-0000-0000-000000000001",
                "item_id": "00000000-0000-0000-0000-000000000002",
                "prompt": "test",
                "response": "test response",
                "metadata": {"cost_usd": 0.005},
                "metric_names": ["cost"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        result = data[0]
        assert result["metric_name"] == "cost"
        assert result["cost_usd"] == 0.005
        assert "confidence" in result
        assert "version" in result


class TestScoreBatch:
    """Tests for POST /metrics/score-batch."""

    def test_score_batch(self, client: TestClient) -> None:
        """Score multiple items with configured metrics."""
        response = client.post(
            "/metrics/score-batch",
            json={
                "items": [
                    {
                        "run_id": "00000000-0000-0000-0000-000000000001",
                        "item_id": "00000000-0000-0000-0000-000000000002",
                        "prompt": "What is Python?",
                        "response": "Python is a language.",
                        "metric_names": ["answer_relevance"],
                    },
                    {
                        "run_id": "00000000-0000-0000-0000-000000000001",
                        "item_id": "00000000-0000-0000-0000-000000000003",
                        "prompt": "What is Rust?",
                        "response": "Rust is a systems language.",
                        "metric_names": ["answer_relevance"],
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_batch_empty_items_rejected(self, client: TestClient) -> None:
        """Empty batch returns 422."""
        response = client.post(
            "/metrics/score-batch",
            json={"items": []},
        )
        assert response.status_code == 422


class TestGetMetricResults:
    """Tests for GET /metrics/runs/{run_id}/results."""

    def test_get_results_empty(self, client: TestClient) -> None:
        """Get results for a run with no results."""
        response = client.get(
            "/metrics/runs/00000000-0000-0000-0000-000000000001/results",
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["items"] == []
        assert data["total"] == 0

    def test_filter_by_metric_name(self, client: TestClient) -> None:
        """Filter results by metric name."""
        response = client.get(
            "/metrics/runs/00000000-0000-0000-0000-000000000001/results",
            params={"metric_name": "answer_relevance"},
        )
        assert response.status_code == 200


class TestGetAggregatedScores:
    """Tests for GET /metrics/runs/{run_id}/scores."""

    def test_get_aggregated_scores_empty(self, client: TestClient) -> None:
        """Get aggregated scores for a run with no results."""
        response = client.get(
            "/metrics/runs/00000000-0000-0000-0000-000000000001/scores",
        )
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["aggregations"] == []


class TestGetItemMetricResults:
    """Tests for GET /metrics/runs/{run_id}/items/{item_id}/results."""

    def test_get_item_results_empty(self, client: TestClient) -> None:
        """Get item results for an item with no results."""
        response = client.get(
            "/metrics/runs/00000000-0000-0000-0000-000000000001/items/00000000-0000-0000-0000-000000000002/results",
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data == []


class TestConfigureEvaluationMetrics:
    """Tests for PATCH /metrics/evaluations/{evaluation_id}/enabled-metrics."""

    def test_configure_metrics_evaluation_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Configuring metrics for a nonexistent evaluation returns 404."""
        response = client.patch(
            "/metrics/evaluations/00000000-0000-0000-0000-000000000001/enabled-metrics",
            json={"metric_names": ["answer_relevance", "correctness"]},
        )
        assert response.status_code == 404

    def test_configure_with_empty_metrics_list(
        self,
        client: TestClient,
    ) -> None:
        """Configuring with empty metrics list is allowed."""
        response = client.patch(
            "/metrics/evaluations/00000000-0000-0000-0000-000000000001/enabled-metrics",
            json={"metric_names": []},
        )
        assert response.status_code in (200, 404)
