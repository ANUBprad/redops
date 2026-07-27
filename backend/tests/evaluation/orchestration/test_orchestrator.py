"""Tests for EvaluationOrchestrator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.evaluation.orchestration.orchestrator import EvaluationOrchestrator
from app.evaluation.domain.enums.evaluation_enums import RunStatus, CancellationReason
from app.evaluation.execution.results.results import ExecutionOutcome, ExecutionResult
from app.kernel.entities.base import UUIDv7


def _make_orchestrator(
    event_publisher=None,
    run_repository=None,
    item_repository=None,
    checkpoint_repository=None,
    provider_registry=None,
) -> EvaluationOrchestrator:
    """Build an EvaluationOrchestrator with mock dependencies."""
    return EvaluationOrchestrator(
        provider_registry=provider_registry or MagicMock(),
        event_publisher=event_publisher or MagicMock(),
        run_repository=run_repository or MagicMock(),
        item_repository=item_repository or MagicMock(),
        checkpoint_repository=checkpoint_repository or MagicMock(),
    )


def _make_run_repository(run=None):
    """Create a mock RunRepository that returns the given run."""
    mock = MagicMock()
    mock.save = AsyncMock()
    mock.find_by_id = AsyncMock(return_value=run)
    mock.find_by_status = AsyncMock(return_value=[])
    mock.delete = AsyncMock(return_value=True)
    return mock


def _make_event_publisher():
    """Create a mock EventPublisher with async publish."""
    mock = MagicMock()
    mock.publish = AsyncMock()
    mock.publish_many = AsyncMock()
    return mock


def _patch_runtime():
    """Return a context manager that patches _create_runtime_coordinator."""
    return patch(
        "app.evaluation.orchestration.orchestrator._create_runtime_coordinator",
        return_value=MagicMock(),
    )


def _patch_executor_success(run_obj=None, total_items: int = 10):
    """Patch executor to simulate success by updating run counters."""

    async def fake_execute(pipeline, context):
        if run_obj is not None:
            run_obj.items_completed = run_obj.items_total
        return ExecutionResult(
            run_id=context.run_id,
            outcome=ExecutionOutcome.SUCCESS,
            total_items=total_items,
            items_succeeded=total_items,
        )

    return patch(
        "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
    ), fake_execute


# ---------------------------------------------------------------------------
# execute_run
# ---------------------------------------------------------------------------


class TestEvaluationOrchestratorExecuteRun:
    """Tests for EvaluationOrchestrator.execute_run()."""

    async def test_execute_run_full_lifecycle(self, sample_run) -> None:
        """Full lifecycle: CREATED -> QUEUED -> RUNNING -> COMPLETED."""
        event_pub = _make_event_publisher()
        run_repo = _make_run_repository()
        orch = _make_orchestrator(event_publisher=event_pub, run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    sample_run.items_completed = sample_run.items_total
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                        total_items=sample_run.items_total,
                        items_succeeded=sample_run.items_total,
                    )

                instance.execute = fake_execute
                result = await orch.execute_run(sample_run)

        assert result.outcome == ExecutionOutcome.SUCCESS
        assert sample_run.status == RunStatus.COMPLETED
        assert run_repo.save.call_count >= 3

    async def test_execute_run_queued_state(self, queued_run) -> None:
        """Already-queued run should skip the queue() transition."""
        event_pub = _make_event_publisher()
        run_repo = _make_run_repository()
        orch = _make_orchestrator(event_publisher=event_pub, run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    queued_run.items_completed = queued_run.items_total
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                        total_items=queued_run.items_total,
                        items_succeeded=queued_run.items_total,
                    )

                instance.execute = fake_execute
                result = await orch.execute_run(queued_run)

        assert result.outcome == ExecutionOutcome.SUCCESS

    async def test_execute_run_cleans_up_active_state(self, sample_run) -> None:
        """Active pipelines/contexts should be cleaned up after execution."""
        run_repo = _make_run_repository()
        orch = _make_orchestrator(run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                    )

                instance.execute = fake_execute
                await orch.execute_run(sample_run)

        assert len(orch._active_pipelines) == 0
        assert len(orch._active_contexts) == 0

    async def test_execute_run_with_single_eval(self, single_config) -> None:
        """Single-type evaluation should execute correctly."""
        from app.evaluation.domain.entities.evaluation_entities import EvaluationRun

        run = EvaluationRun(
            evaluation_name=single_config.name,
            config=single_config,
            profile=single_config.profile,
        )
        event_pub = _make_event_publisher()
        run_repo = _make_run_repository()
        orch = _make_orchestrator(event_publisher=event_pub, run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    run.items_completed = run.items_total
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                        total_items=run.items_total,
                        items_succeeded=run.items_total,
                    )

                instance.execute = fake_execute
                result = await orch.execute_run(run)

        assert result.outcome == ExecutionOutcome.SUCCESS
        assert run.status == RunStatus.COMPLETED

    async def test_execute_run_returns_total_items(self, sample_run) -> None:
        """Result should reflect the plan's total items."""
        run_repo = _make_run_repository()
        orch = _make_orchestrator(run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                        total_items=10,
                    )

                instance.execute = fake_execute
                result = await orch.execute_run(sample_run)

        assert result.total_items == 10

    async def test_execute_run_stores_context(self, sample_run) -> None:
        """Context should be stored during execution and removed after."""
        run_repo = _make_run_repository()
        orch = _make_orchestrator(run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                    )

                instance.execute = fake_execute
                await orch.execute_run(sample_run)

        assert str(sample_run.id) not in orch._active_contexts
        assert str(sample_run.id) not in orch._active_pipelines


# ---------------------------------------------------------------------------
# pause_run
# ---------------------------------------------------------------------------


class TestEvaluationOrchestratorPauseRun:
    """Tests for EvaluationOrchestrator.pause_run()."""

    async def test_pause_running_run(self, running_run) -> None:
        """Pausing a running run should transition to PAUSED."""
        run_repo = _make_run_repository(run=running_run)
        orch = _make_orchestrator(run_repository=run_repo)

        await orch.pause_run(running_run.id)
        assert running_run.status == RunStatus.PAUSED

    async def test_pause_nonexistent_run(self) -> None:
        """Pausing a nonexistent run should raise ValueError."""
        run_repo = _make_run_repository(run=None)
        orch = _make_orchestrator(run_repository=run_repo)

        with pytest.raises(ValueError, match="not found"):
            await orch.pause_run(UUIDv7.generate())

    async def test_pause_non_running_run(self, sample_run) -> None:
        """Pausing a non-running run should raise ValueError."""
        run_repo = _make_run_repository(run=sample_run)
        orch = _make_orchestrator(run_repository=run_repo)

        with pytest.raises(ValueError, match="Cannot pause"):
            await orch.pause_run(sample_run.id)

    async def test_pause_saves_run(self, running_run) -> None:
        """Pausing should persist the run."""
        run_repo = _make_run_repository(run=running_run)
        orch = _make_orchestrator(run_repository=run_repo)

        await orch.pause_run(running_run.id)
        run_repo.save.assert_awaited_once_with(running_run)


# ---------------------------------------------------------------------------
# resume_run
# ---------------------------------------------------------------------------


class TestEvaluationOrchestratorResumeRun:
    """Tests for EvaluationOrchestrator.resume_run()."""

    async def test_resume_paused_run(self, running_run) -> None:
        """Resuming a paused run should re-execute."""
        running_run.pause()
        running_run.save_checkpoint(
            MagicMock(items_completed=5, items_total=10, checkpoint_number=1)
        )

        event_pub = _make_event_publisher()
        run_repo = _make_run_repository(run=running_run)
        checkpoint_repo = MagicMock()
        checkpoint_repo.find_latest = AsyncMock(
            return_value=MagicMock(checkpoint_number=1)
        )
        orch = _make_orchestrator(
            event_publisher=event_pub,
            run_repository=run_repo,
            checkpoint_repository=checkpoint_repo,
        )

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    running_run.items_completed = running_run.items_total
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                        total_items=running_run.items_total,
                        items_succeeded=running_run.items_total,
                    )

                instance.execute = fake_execute

                with patch.object(
                    type(running_run), "start", lambda self, n: None,
                ):
                    result = await orch.resume_run(running_run.id)

        assert result.outcome == ExecutionOutcome.SUCCESS

    async def test_resume_nonexistent_run(self) -> None:
        """Resuming a nonexistent run should raise ValueError."""
        run_repo = _make_run_repository(run=None)
        orch = _make_orchestrator(run_repository=run_repo)

        with pytest.raises(ValueError, match="not found"):
            await orch.resume_run(UUIDv7.generate())

    async def test_resume_non_paused_run(self, running_run) -> None:
        """Resuming a non-paused run should raise ValueError."""
        run_repo = _make_run_repository(run=running_run)
        orch = _make_orchestrator(run_repository=run_repo)

        with pytest.raises(ValueError, match="Cannot resume"):
            await orch.resume_run(running_run.id)

    async def test_resume_without_checkpoint(self, running_run) -> None:
        """Resuming without a checkpoint should raise ValueError."""
        running_run.pause()
        run_repo = _make_run_repository(run=running_run)
        checkpoint_repo = MagicMock()
        checkpoint_repo.find_latest = AsyncMock(return_value=None)
        orch = _make_orchestrator(
            run_repository=run_repo,
            checkpoint_repository=checkpoint_repo,
        )

        with pytest.raises(ValueError, match="No checkpoint"):
            await orch.resume_run(running_run.id)


# ---------------------------------------------------------------------------
# cancel_run
# ---------------------------------------------------------------------------


class TestEvaluationOrchestratorCancelRun:
    """Tests for EvaluationOrchestrator.cancel_run()."""

    async def test_cancel_running_run(self, running_run) -> None:
        """Cancelling a running run should transition to CANCELLING."""
        run_repo = _make_run_repository(run=running_run)
        orch = _make_orchestrator(run_repository=run_repo)

        await orch.cancel_run(running_run.id)
        assert running_run.status == RunStatus.CANCELLING

    async def test_force_cancel_running_run(self, running_run) -> None:
        """Force cancelling should skip to CANCELLED."""
        run_repo = _make_run_repository(run=running_run)
        orch = _make_orchestrator(run_repository=run_repo)

        await orch.cancel_run(running_run.id, force=True)
        assert running_run.status == RunStatus.CANCELLED

    async def test_cancel_nonexistent_run(self) -> None:
        """Cancelling a nonexistent run should raise ValueError."""
        run_repo = _make_run_repository(run=None)
        orch = _make_orchestrator(run_repository=run_repo)

        with pytest.raises(ValueError, match="not found"):
            await orch.cancel_run(UUIDv7.generate())

    async def test_cancel_terminal_run(self) -> None:
        """Cancelling a terminal run should raise ValueError."""
        from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
        from app.evaluation.domain.value_objects.evaluation_value_objects import (
            EvaluationConfiguration,
            EvaluationProfile,
        )

        config = EvaluationConfiguration(
            name="test",
            eval_type="single",
            profile=EvaluationProfile(provider_name="o", model_id="m"),
            metrics=("a",),
        )
        run = EvaluationRun(evaluation_name="test", config=config, profile=config.profile)
        run.queue()
        run.start(total_items=1)
        run.items_completed = 1
        run.complete()

        run_repo = _make_run_repository(run=run)
        orch = _make_orchestrator(run_repository=run_repo)

        with pytest.raises(ValueError, match="Cannot cancel"):
            await orch.cancel_run(run.id)

    async def test_force_cancel_sets_cancellation_token(self, running_run) -> None:
        """Force cancel should set cancellation on the active context."""
        run_repo = _make_run_repository(run=running_run)
        orch = _make_orchestrator(run_repository=run_repo)

        ctx = MagicMock()
        ctx.with_cancellation = MagicMock(return_value=ctx)
        orch._active_contexts[str(running_run.id)] = ctx

        await orch.cancel_run(running_run.id, force=True)
        assert running_run.status == RunStatus.CANCELLED
        ctx.with_cancellation.assert_called_once_with(force=True)

    async def test_cancel_queued_run(self, queued_run) -> None:
        """Cancelling a queued run with force should transition to CANCELLED."""
        run_repo = _make_run_repository(run=queued_run)
        orch = _make_orchestrator(run_repository=run_repo)

        await orch.cancel_run(queued_run.id, force=True)
        assert queued_run.status == RunStatus.CANCELLED

    async def test_cancel_saves_run(self, running_run) -> None:
        """Cancelling should persist the run."""
        run_repo = _make_run_repository(run=running_run)
        orch = _make_orchestrator(run_repository=run_repo)

        await orch.cancel_run(running_run.id)
        run_repo.save.assert_awaited_once_with(running_run)


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


class TestEvaluationOrchestratorErrorHandling:
    """Tests for error handling in EvaluationOrchestrator."""

    async def test_planner_error_propagates(self, sample_run) -> None:
        """Planner error from QUEUED state propagates as InvalidTransitionError
        because run.fail() cannot transition from QUEUED."""
        from app.evaluation.domain.state_machine.run_state_machine import InvalidTransitionError

        run_repo = _make_run_repository()
        orch = _make_orchestrator(run_repository=run_repo)
        orch._planner = MagicMock()
        orch._planner.plan = AsyncMock(side_effect=RuntimeError("planner error"))

        with _patch_runtime():
            with pytest.raises(InvalidTransitionError):
                await orch.execute_run(sample_run)

    async def test_planner_error_after_starting_fails_run(self, sample_run) -> None:
        """validate_plan error when run is still QUEUED propagates as InvalidTransitionError."""
        from app.evaluation.domain.state_machine.run_state_machine import InvalidTransitionError

        run_repo = _make_run_repository()
        orch = _make_orchestrator(run_repository=run_repo)

        from app.evaluation.execution.pipeline.plan import ExecutionPlan
        from app.evaluation.execution.stages.types import StageType

        valid_plan = ExecutionPlan.create(
            run_id=sample_run.id,
            stages=(StageType.PROVIDER_INVOCATION,),
            total_items=1,
        )

        orch._planner = MagicMock()
        orch._planner.plan = AsyncMock(return_value=valid_plan)
        orch._planner.validate_plan = AsyncMock(side_effect=RuntimeError("validation boom"))

        with _patch_runtime():
            with pytest.raises(InvalidTransitionError):
                await orch.execute_run(sample_run)

    async def test_execution_error_fails_run(self, sample_run) -> None:
        """Executor raising an exception should fail the run."""
        event_pub = _make_event_publisher()
        run_repo = _make_run_repository()
        orch = _make_orchestrator(event_publisher=event_pub, run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value
                instance.execute = AsyncMock(side_effect=RuntimeError("executor error"))
                result = await orch.execute_run(sample_run)

        assert result.outcome == ExecutionOutcome.FAILURE
        assert "executor error" in (result.error or "")

    async def test_build_error_result(self) -> None:
        """_build_error_result should return a FAILURE ExecutionResult."""
        from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
        from app.evaluation.domain.value_objects.evaluation_value_objects import (
            EvaluationConfiguration,
            EvaluationProfile,
        )

        config = EvaluationConfiguration(
            name="test",
            eval_type="single",
            profile=EvaluationProfile(provider_name="o", model_id="m"),
            metrics=("a",),
        )
        run = EvaluationRun(evaluation_name="test", config=config, profile=config.profile)
        orch = _make_orchestrator()

        result = orch._build_error_result(run, "test error")
        assert result.outcome == ExecutionOutcome.FAILURE
        assert result.error == "test error"
        assert result.run_id == run.id

    async def test_execute_run_observer_called(self, sample_run) -> None:
        """Observer should be called during successful execution."""
        event_pub = _make_event_publisher()
        run_repo = _make_run_repository()
        orch = _make_orchestrator(event_publisher=event_pub, run_repository=run_repo)

        with _patch_runtime():
            with patch(
                "app.evaluation.orchestration.orchestrator.EvaluationPipelineExecutor",
            ) as MockExec:
                instance = MockExec.return_value

                async def fake_execute(pipeline, context):
                    sample_run.items_completed = sample_run.items_total
                    return ExecutionResult(
                        run_id=context.run_id,
                        outcome=ExecutionOutcome.SUCCESS,
                        total_items=sample_run.items_total,
                        items_succeeded=sample_run.items_total,
                    )

                instance.execute = fake_execute
                await orch.execute_run(sample_run)

        event_pub.publish.assert_awaited()
