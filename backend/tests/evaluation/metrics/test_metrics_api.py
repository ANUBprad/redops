"""Integration tests for metrics API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.metrics import metrics_router
from app.core.dependencies import CurrentUser, get_current_user, get_db_session


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock async session for testing."""
    session = MagicMock(spec=AsyncSession)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar.return_value = 0
    mock_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add_all = MagicMock()

    return session


@pytest.fixture
def test_app(mock_session: MagicMock) -> FastAPI:
    """Create a test FastAPI app with mocked dependencies."""
    app = FastAPI()
    app.include_router(metrics_router)
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id="test-user")
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
        assert "relevance" in names
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
                "metric_names": ["relevance", "correctness"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {r["metric_name"] for r in data}
        assert names == {"relevance", "correctness"}

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
                        "metric_names": ["relevance"],
                    },
                    {
                        "run_id": "00000000-0000-0000-0000-000000000001",
                        "item_id": "00000000-0000-0000-0000-000000000003",
                        "prompt": "What is Rust?",
                        "response": "Rust is a systems language.",
                        "metric_names": ["relevance"],
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
            params={"metric_name": "relevance"},
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
            json={"metric_names": ["relevance", "correctness"]},
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
