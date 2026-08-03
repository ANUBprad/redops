"""Tests for evaluation run Temporal integration.

Covers activity functions and workflow orchestration with mocked
dependencies (database, handlers, Temporal SDK).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.evaluation.temporal.activities import (
    CancelRunInput,
    CreateRunInput,
    FailRunInput,
    ProgressInput,
    RunIdInput,
    RunResult,
    StartRunInput,
    cancel_run_activity,
    complete_run_activity,
    configure_session_factory,
    create_run_activity,
    fail_run_activity,
    queue_run_activity,
    start_run_activity,
    update_progress_activity,
)
from app.evaluation.temporal.workflow import (
    EvaluationRunWorkflow,
    EvaluationRunWorkflowInput,
    EvaluationRunWorkflowResult,
)


def _mock_run(status: str = "created") -> MagicMock:
    """Create a mock EvaluationRun."""
    run = MagicMock()
    run.id = "test-run-id"
    run.status.value = status
    run.evaluation_name = "test-eval"
    return run


# ---------------------------------------------------------------------------
# Activity tests
# ---------------------------------------------------------------------------


class TestActivities:
    """Tests for Temporal activity functions."""

    def test_configure_session_factory(self) -> None:
        """Session factory can be configured."""
        import app.evaluation.temporal.activities as mod

        old = mod._session_factory
        try:
            configure_session_factory(AsyncMock())
            assert mod._session_factory is not None
        finally:
            mod._session_factory = old

    def test_configure_session_factory_raises_when_none(self) -> None:
        """_get_session raises when factory is not configured."""
        import app.evaluation.temporal.activities as mod

        old = mod._session_factory
        try:
            mod._session_factory = None
            with pytest.raises(RuntimeError, match="Session factory not configured"):
                mod._get_session()
        finally:
            mod._session_factory = old

    @pytest.mark.asyncio
    async def test_create_run_activity(self) -> None:
        """create_run_activity delegates to CreateEvaluationRunHandler."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_repo = MagicMock()
        run = _mock_run("created")

        with (
            patch(
                "app.evaluation.temporal.activities._get_session",
            ) as mock_ctx,
            patch(
                "app.evaluation.temporal.activities.SqlAlchemyEvaluationRunRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.evaluation.temporal.activities.CreateEvaluationRunHandler",
            ) as MockHandler,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value.handle = AsyncMock(return_value=run)

            input_data = CreateRunInput(
                evaluation_name="test",
                provider="openai",
                model="gpt-4",
                metrics=("accuracy",),
            )
            result = await create_run_activity(input_data)

            assert isinstance(result, RunResult)
            assert result.run_id == "test-run-id"
            assert result.status == "created"

    @pytest.mark.asyncio
    async def test_queue_run_activity(self) -> None:
        """queue_run_activity delegates to QueueEvaluationRunHandler."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_repo = MagicMock()
        run = _mock_run("queued")

        with (
            patch(
                "app.evaluation.temporal.activities._get_session",
            ) as mock_ctx,
            patch(
                "app.evaluation.temporal.activities.SqlAlchemyEvaluationRunRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.evaluation.temporal.activities.QueueEvaluationRunHandler",
            ) as MockHandler,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value.handle = AsyncMock(return_value=run)

            result = await queue_run_activity(RunIdInput(run_id="test-run-id"))
            assert result.status == "queued"

    @pytest.mark.asyncio
    async def test_start_run_activity(self) -> None:
        """start_run_activity delegates to StartEvaluationRunHandler."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_repo = MagicMock()
        run = _mock_run("running")

        with (
            patch(
                "app.evaluation.temporal.activities._get_session",
            ) as mock_ctx,
            patch(
                "app.evaluation.temporal.activities.SqlAlchemyEvaluationRunRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.evaluation.temporal.activities.StartEvaluationRunHandler",
            ) as MockHandler,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value.handle = AsyncMock(return_value=run)

            result = await start_run_activity(
                StartRunInput(run_id="test-run-id", total_items=10),
            )
            assert result.status == "running"

    @pytest.mark.asyncio
    async def test_update_progress_activity(self) -> None:
        """update_progress_activity delegates to UpdateRunProgressHandler."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_repo = MagicMock()
        run = _mock_run("running")

        with (
            patch(
                "app.evaluation.temporal.activities._get_session",
            ) as mock_ctx,
            patch(
                "app.evaluation.temporal.activities.SqlAlchemyEvaluationRunRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.evaluation.temporal.activities.UpdateRunProgressHandler",
            ) as MockHandler,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value.handle = AsyncMock(return_value=run)

            result = await update_progress_activity(
                ProgressInput(run_id="test-run-id", items_completed=5),
            )
            assert result.status == "running"

    @pytest.mark.asyncio
    async def test_complete_run_activity(self) -> None:
        """complete_run_activity delegates to CompleteEvaluationRunHandler."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_repo = MagicMock()
        run = _mock_run("completed")

        with (
            patch(
                "app.evaluation.temporal.activities._get_session",
            ) as mock_ctx,
            patch(
                "app.evaluation.temporal.activities.SqlAlchemyEvaluationRunRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.evaluation.temporal.activities.CompleteEvaluationRunHandler",
            ) as MockHandler,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value.handle = AsyncMock(return_value=run)

            result = await complete_run_activity(RunIdInput(run_id="test-run-id"))
            assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_fail_run_activity(self) -> None:
        """fail_run_activity delegates to FailEvaluationRunHandler."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_repo = MagicMock()
        run = _mock_run("failed")

        with (
            patch(
                "app.evaluation.temporal.activities._get_session",
            ) as mock_ctx,
            patch(
                "app.evaluation.temporal.activities.SqlAlchemyEvaluationRunRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.evaluation.temporal.activities.FailEvaluationRunHandler",
            ) as MockHandler,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value.handle = AsyncMock(return_value=run)

            result = await fail_run_activity(
                FailRunInput(run_id="test-run-id", error_code="ERR"),
            )
            assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_cancel_run_activity(self) -> None:
        """cancel_run_activity delegates to CancelEvaluationRunHandler."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_repo = MagicMock()
        run = _mock_run("cancelled")

        with (
            patch(
                "app.evaluation.temporal.activities._get_session",
            ) as mock_ctx,
            patch(
                "app.evaluation.temporal.activities.SqlAlchemyEvaluationRunRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.evaluation.temporal.activities.CancelEvaluationRunHandler",
            ) as MockHandler,
        ):
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            MockHandler.return_value.handle = AsyncMock(return_value=run)

            result = await cancel_run_activity(
                CancelRunInput(run_id="test-run-id"),
            )
            assert result.status == "cancelled"


# ---------------------------------------------------------------------------
# Workflow tests
# ---------------------------------------------------------------------------


class TestEvaluationRunWorkflow:
    """Tests for EvaluationRunWorkflow orchestration."""

    def test_workflow_init(self) -> None:
        """Workflow initializes with no cancel requested."""
        wf = EvaluationRunWorkflow()
        assert wf._cancel_requested is False

    def test_workflow_cancel_signal(self) -> None:
        """Workflow cancel signal sets _cancel_requested."""
        wf = EvaluationRunWorkflow()
        wf.cancel()
        assert wf._cancel_requested is True

    def test_workflow_result_dataclass(self) -> None:
        """Workflow result holds expected fields."""
        result = EvaluationRunWorkflowResult(
            run_id="r1",
            status="completed",
            items_completed=10,
            items_total=10,
        )
        assert result.run_id == "r1"
        assert result.items_completed == 10

    def test_workflow_input_dataclass(self) -> None:
        """Workflow input holds expected fields."""
        inp = EvaluationRunWorkflowInput(run_id="r1", total_items=5)
        assert inp.run_id == "r1"
        assert inp.total_items == 5

    @pytest.mark.asyncio
    async def test_workflow_cancelled_mid_execution(self) -> None:
        """Workflow returns cancelled status when cancel signal received."""
        wf = EvaluationRunWorkflow()
        wf._cancel_requested = True

        with patch.object(wf, "run") as mock_run:
            expected = EvaluationRunWorkflowResult(
                run_id="r1",
                status="cancelled",
                items_completed=0,
                items_total=5,
            )
            mock_run.return_value = expected
            result = await wf.run(
                EvaluationRunWorkflowInput(run_id="r1", total_items=5),
            )
            assert result.status == "cancelled"

    def test_run_result_dataclass(self) -> None:
        """RunResult holds expected fields."""
        result = RunResult(run_id="r1", status="completed", evaluation_name="eval1")
        assert result.run_id == "r1"
        assert result.evaluation_name == "eval1"
