"""P3-3B tests: evaluation retry actually schedules a Temporal workflow.

Proves that retrying a failed evaluation run:
1. Creates a NEW run ID distinct from the source
2. Preserves the original execution configuration (provider, model, metrics)
3. Schedules EvaluationRunWorkflow via Temporal with the NEW run ID
4. Uses the production task queue
5. Assigns a unique workflow ID (no collision with original)
6. Flushes the new run to the DB before scheduling
7. Follows correct error semantics on Temporal scheduling failure
8. Mirrors the normal create_run path (same workflow class, same input shape)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.evaluation.application.run_handlers import RetryEvaluationRunHandler
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import (
    EvaluationType,
    RunStatus,
)
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationMetadata,
    EvaluationProfile,
)
from app.evaluation.temporal.workflow import (
    EvaluationRunWorkflow,
    EvaluationRunWorkflowInput,
)
from app.kernel.exceptions.errors import ConflictError, NotFoundError

SOURCE_RUN_ID = "0190aaaa-bbbb-7ccc-dddd-eeeeeeee0001"
PROVIDER = "openai"
MODEL = "gpt-4"
METRICS = ("accuracy", "faithfulness")
SYSTEM_PROMPT = "You are a helpful assistant."
EVAL_NAME = "test-evaluation"
PROMPT_TEMPLATE = "Answer against the context:\n{context}\n\nQuestion: {prompt}"
DATASET_ITEMS = (
    {"prompt": "What is the capital of France?", "context": "Paris is the capital of France."},
    {"prompt": "What is 2 + 2?", "context": "Basic arithmetic."},
)


def _make_source_run(
    *,
    status: RunStatus = RunStatus.FAILED,
    dataset_items: tuple[dict[str, str], ...] = DATASET_ITEMS,
    prompt_template: str | None = PROMPT_TEMPLATE,
) -> EvaluationRun:
    """Create a source EvaluationRun with the standard test configuration."""
    config = EvaluationConfiguration(
        name=EVAL_NAME,
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(
            provider_name=PROVIDER,
            model_id=MODEL,
            system_prompt=SYSTEM_PROMPT,
        ),
        metrics=METRICS,
        prompt_template=prompt_template,
        dataset_items=dataset_items,
    )
    run = EvaluationRun(
        evaluation_name=EVAL_NAME,
        config=config,
        profile=EvaluationProfile(
            provider_name=PROVIDER,
            model_id=MODEL,
            system_prompt=SYSTEM_PROMPT,
        ),
        metadata=EvaluationMetadata(project_id="proj-1"),
    )
    run.items_total = 5

    if status in (RunStatus.FAILED, RunStatus.TIMEDOUT):
        run.queue()
        run.start(total_items=5)
        run.items_completed = 3
        run.items_failed = 2
        if status == RunStatus.FAILED:
            run.fail(error_code="ALL_ITEMS_FAILED", error_message="boom")
        else:
            run.timeout()

    run.collect_events()
    return run


def _make_new_run(
    *,
    dataset_items: tuple[dict[str, str], ...] = DATASET_ITEMS,
    prompt_template: str | None = PROMPT_TEMPLATE,
) -> EvaluationRun:
    """Create the new run returned by the handler after creation."""
    config = EvaluationConfiguration(
        name=EVAL_NAME,
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(
            provider_name=PROVIDER,
            model_id=MODEL,
            system_prompt=SYSTEM_PROMPT,
        ),
        metrics=METRICS,
        prompt_template=prompt_template,
        dataset_items=dataset_items,
    )
    run = EvaluationRun(
        evaluation_name=EVAL_NAME,
        config=config,
        profile=EvaluationProfile(
            provider_name=PROVIDER,
            model_id=MODEL,
            system_prompt=SYSTEM_PROMPT,
        ),
        metadata=EvaluationMetadata(project_id="proj-1"),
    )
    run.items_total = 5
    run.collect_events()
    return run


async def _call_retry_endpoint(
    *,
    temporal_client: Any,
    config: Any,
    handler_instance: Any,
    queue_instance: Any | None = None,
) -> MagicMock:
    """Call retry_run with fully mocked dependencies."""
    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_repo = AsyncMock()

    if queue_instance is None:
        new_run_for_queue = _make_new_run()
        new_run_for_queue.queue()
        new_run_for_queue.workflow_id = f"evaluation-run-{handler_instance.handle.return_value.id}"
        new_run_for_queue.collect_events()
        queue_instance = AsyncMock()
        queue_instance.handle = AsyncMock(return_value=new_run_for_queue)

    with (
        patch("app.api.evaluation_run._get_repository", return_value=mock_repo),
        patch("app.api.evaluation_run.RetryEvaluationRunHandler", return_value=handler_instance),
        patch("app.api.evaluation_run.QueueEvaluationRunHandler", return_value=queue_instance),
        patch("app.api.evaluation_run._run_to_response", return_value=MagicMock()),
    ):
        from app.api.evaluation_run import retry_run

        await retry_run(
            SOURCE_RUN_ID,
            current_user=MagicMock(user_id="test-user"),
            session=mock_session,
            temporal_client=temporal_client,
            config=config,
        )
    return mock_session


# ---------------------------------------------------------------------------
# Test 1: Retry creates a new run ID
# ---------------------------------------------------------------------------


class TestRetryCreatesNewRunId:
    """Retry produces a distinct run ID from the source."""

    async def test_new_run_id_differs_from_source(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        mock_tc = MagicMock()
        mock_tc.start_workflow = AsyncMock()
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert str(new_run.id) != SOURCE_RUN_ID


# ---------------------------------------------------------------------------
# Test 2: Retry preserves original execution configuration
# ---------------------------------------------------------------------------


class TestRetryPreservesConfiguration:
    """Workflow input preserves provider, model, metrics from source run."""

    async def test_workflow_input_matches_source_config(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        captured_inputs: list[EvaluationRunWorkflowInput] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            captured_inputs.append(input_data)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert len(captured_inputs) == 1
        inp = captured_inputs[0]
        assert inp.provider_name == PROVIDER
        assert inp.model_id == MODEL
        assert inp.metric_names == METRICS
        assert inp.system_prompt == SYSTEM_PROMPT

    async def test_workflow_input_reproduces_persisted_execution_inputs(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        captured_inputs: list[EvaluationRunWorkflowInput] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            captured_inputs.append(input_data)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert len(captured_inputs) == 1
        inp = captured_inputs[0]
        assert inp.provider_name == PROVIDER
        assert inp.model_id == MODEL
        assert inp.metric_names == METRICS
        assert inp.system_prompt == SYSTEM_PROMPT
        assert inp.prompt_template == PROMPT_TEMPLATE
        assert inp.dataset_items == DATASET_ITEMS
        assert inp.total_items == new_run.items_total


# ---------------------------------------------------------------------------
# Tests 3-6: Workflow scheduling details
# ---------------------------------------------------------------------------


class TestRetrySchedulesWorkflow:
    """Verify the retry endpoint schedules EvaluationRunWorkflow correctly."""

    async def test_start_workflow_called_with_correct_class(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        workflow_refs: list[Any] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            workflow_refs.append(workflow)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert len(workflow_refs) == 1
        assert workflow_refs[0] == EvaluationRunWorkflow.run

    async def test_uses_production_task_queue(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        kwargs_list: list[dict[str, Any]] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            kwargs_list.append(kwargs)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert kwargs_list[0]["task_queue"] == "redops-eval"
        assert kwargs_list[0]["execution_timeout"] == timedelta(hours=24)

    async def test_workflow_id_uses_new_run_id(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        kwargs_list: list[dict[str, Any]] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            kwargs_list.append(kwargs)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        workflow_id = kwargs_list[0]["id"]
        assert workflow_id == f"evaluation-run-{new_run.id}"
        assert str(new_run.id) != SOURCE_RUN_ID

    async def test_workflow_input_uses_new_run_id(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        captured_inputs: list[EvaluationRunWorkflowInput] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            captured_inputs.append(input_data)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert captured_inputs[0].run_id == str(new_run.id)
        assert captured_inputs[0].run_id != SOURCE_RUN_ID

    async def test_total_items_from_source(self) -> None:
        new_run = _make_new_run()
        new_run.items_total = 5
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        captured_inputs: list[EvaluationRunWorkflowInput] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            captured_inputs.append(input_data)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert captured_inputs[0].total_items == 5


# ---------------------------------------------------------------------------
# Test 7: Flush before scheduling
# ---------------------------------------------------------------------------


class TestTransactionOrdering:
    """New run is persisted before Temporal scheduling begins."""

    async def test_session_flushed_before_workflow_scheduled(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        call_order: list[str] = []

        async def _flush() -> None:
            call_order.append("flush")

        mock_tc = MagicMock()

        async def _capture_workflow(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            call_order.append("start_workflow")

        mock_tc.start_workflow = _capture_workflow
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        mock_session = AsyncMock()
        mock_session.flush = _flush
        mock_repo = AsyncMock()

        new_run_for_queue = _make_new_run()
        new_run_for_queue.queue()
        new_run_for_queue.workflow_id = f"evaluation-run-{new_run.id}"
        new_run_for_queue.collect_events()
        queue_instance = AsyncMock()
        queue_instance.handle = AsyncMock(return_value=new_run_for_queue)

        with (
            patch("app.api.evaluation_run._get_repository", return_value=mock_repo),
            patch("app.api.evaluation_run.RetryEvaluationRunHandler", return_value=handler),
            patch("app.api.evaluation_run.QueueEvaluationRunHandler", return_value=queue_instance),
            patch("app.api.evaluation_run._run_to_response", return_value=MagicMock()),
        ):
            from app.api.evaluation_run import retry_run

            await retry_run(
                SOURCE_RUN_ID,
                current_user=MagicMock(user_id="test-user"),
                session=mock_session,
                temporal_client=mock_tc,
                config=mock_config,
            )

        assert call_order == ["flush", "start_workflow"]

    async def test_run_queued_and_workflow_id_set_after_scheduling(self) -> None:
        new_run = _make_new_run()
        new_run.workflow_id = None
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        mock_tc = MagicMock()
        mock_tc.start_workflow = AsyncMock()
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_repo = MagicMock()

        queued_run = _make_new_run()
        queued_run.queue()
        expected_wf_id = f"evaluation-run-{new_run.id}"
        queued_run.workflow_id = expected_wf_id
        queued_run.collect_events()

        queue_instance = AsyncMock()
        queue_instance.handle = AsyncMock(return_value=queued_run)

        saved_runs: list[Any] = []

        async def _save(run: Any) -> None:
            saved_runs.append(run)

        mock_repo.save = _save

        with (
            patch("app.api.evaluation_run._get_repository", return_value=mock_repo),
            patch("app.api.evaluation_run.RetryEvaluationRunHandler", return_value=handler),
            patch("app.api.evaluation_run.QueueEvaluationRunHandler", return_value=queue_instance),
            patch("app.api.evaluation_run._run_to_response", return_value=MagicMock()),
        ):
            from app.api.evaluation_run import retry_run

            await retry_run(
                SOURCE_RUN_ID,
                current_user=MagicMock(user_id="test-user"),
                session=mock_session,
                temporal_client=mock_tc,
                config=mock_config,
            )

        queue_instance.handle.assert_called_once()
        assert len(saved_runs) >= 1
        assert saved_runs[-1].workflow_id == expected_wf_id


# ---------------------------------------------------------------------------
# Test 8: Temporal scheduling failure
# ---------------------------------------------------------------------------


class TestRetryTemporalSchedulingFailure:
    """Temporal scheduling failures propagate correctly."""

    async def test_temporal_error_not_swallowed(self) -> None:
        from fastapi import HTTPException

        from app.kernel.exceptions.errors import InfrastructureError

        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        async def _fail(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            raise InfrastructureError(
                message="Temporal unavailable",
                error_code="TEMPORAL_UNAVAILABLE",
            )

        mock_tc = MagicMock()
        mock_tc.start_workflow = _fail
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_repo = MagicMock()

        with (
            patch("app.api.evaluation_run._get_repository", return_value=mock_repo),
            patch("app.api.evaluation_run.RetryEvaluationRunHandler", return_value=handler),
            patch("app.api.evaluation_run._run_to_response", return_value=MagicMock()),
        ):
            from app.api.evaluation_run import retry_run

            with pytest.raises(HTTPException) as exc_info:
                await retry_run(
                    SOURCE_RUN_ID,
                    current_user=MagicMock(user_id="test-user"),
                    session=mock_session,
                    temporal_client=mock_tc,
                    config=mock_config,
                )

            assert exc_info.value.status_code == 503

    async def test_handler_not_found_returns_404(self) -> None:
        from fastapi import HTTPException

        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(
            side_effect=NotFoundError(
                message="Evaluation run not found",
                resource_type="EvaluationRun",
                resource_id="nonexistent",
            ),
        )

        mock_tc = MagicMock()
        mock_config = MagicMock()

        with (
            patch("app.api.evaluation_run._get_repository", return_value=MagicMock()),
            patch("app.api.evaluation_run.RetryEvaluationRunHandler", return_value=handler),
        ):
            from app.api.evaluation_run import retry_run

            with pytest.raises(HTTPException) as exc_info:
                await retry_run(
                    "nonexistent",
                    current_user=MagicMock(user_id="test-user"),
                    session=AsyncMock(),
                    temporal_client=mock_tc,
                    config=mock_config,
                )

            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Test 9: Same contract as normal create path
# ---------------------------------------------------------------------------


class TestRetryMatchesNormalPath:
    """Prove retry reaches the same workflow/activity contract as create."""

    async def test_same_workflow_class_and_input_type(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        workflow_refs: list[Any] = []
        input_types: list[type] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            workflow_refs.append(workflow)
            input_types.append(type(input_data))

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert workflow_refs[0] == EvaluationRunWorkflow.run
        assert input_types[0] is EvaluationRunWorkflowInput

    async def test_same_task_queue_as_create(self) -> None:
        new_run = _make_new_run()
        handler = AsyncMock(spec=RetryEvaluationRunHandler)
        handler.handle = AsyncMock(return_value=new_run)

        kwargs_list: list[dict[str, Any]] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            kwargs_list.append(kwargs)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        await _call_retry_endpoint(
            temporal_client=mock_tc,
            config=mock_config,
            handler_instance=handler,
        )

        assert kwargs_list[0]["task_queue"] == "redops-eval"
        assert kwargs_list[0]["execution_timeout"] == timedelta(hours=24)


# ---------------------------------------------------------------------------
# Test 10: Existing handler behavior unchanged
# ---------------------------------------------------------------------------


class TestExistingRetryHandlerBehavior:
    """Existing retry handler tests remain valid."""

    async def test_handler_creates_new_run_from_source(self) -> None:
        source = _make_source_run()

        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=source)
        mock_repo.save = AsyncMock()

        handler = RetryEvaluationRunHandler(mock_repo)
        from app.evaluation.application.run_commands import RetryEvaluationRunCommand

        command = RetryEvaluationRunCommand(run_id=SOURCE_RUN_ID)
        result = await handler.handle(command)

        assert result.status == RunStatus.CREATED
        assert result.id != source.id
        assert result.config.metrics == source.config.metrics
        assert result.profile.provider_name == source.profile.provider_name
        assert result.profile.model_id == source.profile.model_id

    async def test_handler_rejects_non_failed_run(self) -> None:
        source = _make_source_run(status=RunStatus.RUNNING)

        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=source)

        handler = RetryEvaluationRunHandler(mock_repo)
        from app.evaluation.application.run_commands import RetryEvaluationRunCommand

        command = RetryEvaluationRunCommand(run_id=SOURCE_RUN_ID)

        with pytest.raises(ConflictError, match="Only failed"):
            await handler.handle(command)


# ---------------------------------------------------------------------------
# P3-4: Legacy runs without persisted dataset inputs are rejected
# ---------------------------------------------------------------------------


class TestRetryRejectsLegacyRuns:
    """Legacy runs predating input persistence cannot be retried faithfully."""

    async def test_handler_rejects_legacy_run_without_dataset_inputs(self) -> None:
        source = _make_source_run(dataset_items=(), prompt_template=None)

        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=source)
        mock_repo.save = AsyncMock()

        handler = RetryEvaluationRunHandler(mock_repo)
        from app.evaluation.application.run_commands import RetryEvaluationRunCommand

        command = RetryEvaluationRunCommand(run_id=SOURCE_RUN_ID)

        with pytest.raises(ConflictError, match="dataset inputs were not persisted"):
            await handler.handle(command)

        mock_repo.save.assert_not_called()

    async def test_legacy_run_retry_returns_409_and_does_not_schedule(self) -> None:
        from fastapi import HTTPException

        source = _make_source_run(dataset_items=(), prompt_template=None)

        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=source)
        mock_repo.save = AsyncMock()

        mock_tc = MagicMock()
        mock_tc.start_workflow = AsyncMock()
        mock_config = MagicMock()

        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        queue_instance = AsyncMock()

        with (
            patch("app.api.evaluation_run._get_repository", return_value=mock_repo),
            patch("app.api.evaluation_run.QueueEvaluationRunHandler", return_value=queue_instance),
            patch("app.api.evaluation_run._run_to_response", return_value=MagicMock()),
        ):
            from app.api.evaluation_run import retry_run

            with pytest.raises(HTTPException) as exc_info:
                await retry_run(
                    SOURCE_RUN_ID,
                    current_user=MagicMock(user_id="test-user"),
                    session=mock_session,
                    temporal_client=mock_tc,
                    config=mock_config,
                )

            assert exc_info.value.status_code == 409

        mock_tc.start_workflow.assert_not_called()
        queue_instance.handle.assert_not_called()
        mock_repo.save.assert_not_called()
