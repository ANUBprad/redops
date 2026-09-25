"""Tests for experiment analytics services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.analytics.services.experiment_analytics import (
    ExperimentComparisonService,
    MetricDistributionService,
    PassFailSummaryService,
)
from app.evaluation.domain.contracts.evaluation_contracts import (
    MetricResultRepository,
    RunRepository,
)
from app.evaluation.domain.contracts.experiment_contracts import ExperimentRepository
from app.evaluation.domain.entities.experiment import Experiment
from app.evaluation.domain.enums.experiment_enums import ExperimentStatus
from app.evaluation.domain.value_objects.experiment_value_objects import ExperimentName
from app.evaluation.metrics.domain import MetricResult
from app.kernel.entities.base import UUIDv7


def _make_experiment(
    *,
    entity_id: UUIDv7 | None = None,
    project_id: str = "proj-1",
    name: str = "test-experiment",
    status: ExperimentStatus = ExperimentStatus.ACTIVE,
    baseline_run_id: str | None = None,
) -> Experiment:
    """Create an experiment for testing."""
    exp = Experiment.create(
        project_id=project_id,
        name=ExperimentName(value=name),
    )
    if status == ExperimentStatus.ACTIVE:
        exp.activate()
    elif status == ExperimentStatus.COMPLETED:
        exp.activate()
        exp.complete()
    if baseline_run_id:
        exp.set_baseline(baseline_run_id)
    exp.collect_events()  # clear events
    return exp


class TestExperimentComparisonService:
    """Tests for ExperimentComparisonService."""

    def test_returns_not_found_for_missing_experiment(self) -> None:
        mock_experiment_repo = AsyncMock(spec=ExperimentRepository)
        mock_experiment_repo.find_by_id = AsyncMock(return_value=None)
        mock_run_repo = AsyncMock(spec=RunRepository)
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)

        service = ExperimentComparisonService(
            experiment_repo=mock_experiment_repo,
            run_repo=mock_run_repo,
            metric_repo=mock_metric_repo,
        )

        import asyncio

        result = asyncio.run(service.compare_experiment_runs(str(UUIDv7.generate())))

        assert result.summary == "Experiment not found"

    def test_returns_empty_when_no_runs(self) -> None:
        experiment = _make_experiment()
        mock_experiment_repo = AsyncMock(spec=ExperimentRepository)
        mock_experiment_repo.find_by_id = AsyncMock(return_value=experiment)
        mock_run_repo = AsyncMock(spec=RunRepository)
        mock_run_repo.list = AsyncMock(return_value=MagicMock(items=[]))
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)

        service = ExperimentComparisonService(
            experiment_repo=mock_experiment_repo,
            run_repo=mock_run_repo,
            metric_repo=mock_metric_repo,
        )

        import asyncio

        result = asyncio.run(service.compare_experiment_runs(str(experiment.id)))

        assert "No runs found" in result.summary


class TestMetricDistributionService:
    """Tests for MetricDistributionService."""

    def test_empty_distribution(self) -> None:
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)
        mock_metric_repo.find_by_run_id = AsyncMock(return_value=[])

        service = MetricDistributionService(metric_repo=mock_metric_repo)

        import asyncio

        result = asyncio.run(service.get_distribution(run_id=str(UUIDv7.generate())))

        assert result["bins"] == []
        assert result["total"] == 0

    def test_distribution_with_scores(self) -> None:
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)
        mock_results = []
        for i in range(10):
            mr = MagicMock(spec=MetricResult)
            mr.score = i / 10.0
            mr.error = None
            mr.metric_name = "hallucination"
            mock_results.append(mr)
        mock_metric_repo.find_by_run_id = AsyncMock(return_value=mock_results)

        service = MetricDistributionService(metric_repo=mock_metric_repo)

        import asyncio

        result = asyncio.run(
            service.get_distribution(
                run_id=str(UUIDv7.generate()),
                metric_name="hallucination",
                bins=5,
            )
        )

        assert result["total"] == 10
        assert len(result["bins"]) == 6  # bins + 1 edges
        assert len(result["counts"]) == 5
        assert sum(result["counts"]) == 10


class TestPassFailSummaryService:
    """Tests for PassFailSummaryService."""

    def test_empty_summary(self) -> None:
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)
        mock_metric_repo.find_by_run_id = AsyncMock(return_value=[])

        service = PassFailSummaryService(metric_repo=mock_metric_repo)

        import asyncio

        result = asyncio.run(service.get_summary(run_id=str(UUIDv7.generate())))

        assert result["overall_pass"] is True
        assert result["total_metrics"] == 0

    def test_pass_with_threshold(self) -> None:
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)
        mr = MagicMock(spec=MetricResult)
        mr.score = 0.9
        mr.error = None
        mr.metric_name = "faithfulness"
        mock_metric_repo.find_by_run_id = AsyncMock(return_value=[mr])

        service = PassFailSummaryService(metric_repo=mock_metric_repo)

        import asyncio

        result = asyncio.run(
            service.get_summary(
                run_id=str(UUIDv7.generate()),
                thresholds={"faithfulness": 0.8},
            )
        )

        assert result["overall_pass"] is True
        assert result["passed_metrics"] == 1
        assert result["metrics"]["faithfulness"]["passed"] is True

    def test_fail_below_threshold(self) -> None:
        mock_metric_repo = AsyncMock(spec=MetricResultRepository)
        mr = MagicMock(spec=MetricResult)
        mr.score = 0.5
        mr.error = None
        mr.metric_name = "toxicity"
        mock_metric_repo.find_by_run_id = AsyncMock(return_value=[mr])

        service = PassFailSummaryService(metric_repo=mock_metric_repo)

        import asyncio

        result = asyncio.run(
            service.get_summary(
                run_id=str(UUIDv7.generate()),
                thresholds={"toxicity": 0.8},
            )
        )

        assert result["overall_pass"] is False
        assert result["failed_metrics"] == 1
        assert result["metrics"]["toxicity"]["passed"] is False
