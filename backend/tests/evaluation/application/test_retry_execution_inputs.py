"""P3-4 tests: create/retry handlers preserve execution inputs.

Covers the application-layer contract:
10. CreateEvaluationRunHandler persists dataset_items in the run configuration.
11. CreateEvaluationRunHandler persists prompt_template in the run configuration.
12. The create endpoint schedules a workflow carrying the SAME inputs as the request.
13. RetryEvaluationRunHandler copies dataset_items from the source run.
14. RetryEvaluationRunHandler copies prompt_template from the source run.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.evaluation.application.run_commands import (
    CreateEvaluationRunCommand,
    RetryEvaluationRunCommand,
)
from app.evaluation.application.run_handlers import (
    CreateEvaluationRunHandler,
    RetryEvaluationRunHandler,
)
from app.evaluation.domain.entities.evaluation_entities import EvaluationRun
from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
)
from app.schemas.evaluation_run import (
    CreateEvaluationRunRequest,
    DatasetItemRequest,
)

PROMPT_TEMPLATE = "Answer using only the context.\n{context}\nQuestion: {prompt}"
DATASET_ITEMS = (
    {"prompt": "What is the capital of France?", "context": "Paris is the capital."},
    {"prompt": "What is 2 + 2?", "context": "Two plus two is four."},
)


def _make_source_run(
    dataset_items: tuple[dict[str, str], ...] = DATASET_ITEMS,
    prompt_template: str | None = PROMPT_TEMPLATE,
) -> EvaluationRun:
    """Build a FAILED run carrying the given persisted inputs."""
    config = EvaluationConfiguration(
        name="retry-source",
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        metrics=("accuracy",),
        prompt_template=prompt_template,
        dataset_items=dataset_items,
    )
    run = EvaluationRun(
        evaluation_name="retry-source",
        config=config,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
    )
    run.queue()
    run.start(total_items=2)
    run.fail(error_code="ERR", error_message="boom")
    run.collect_events()
    return run


def _make_queued_run() -> EvaluationRun:
    """Build a QUEUED run as returned by QueueEvaluationRunHandler."""
    run = EvaluationRun(
        evaluation_name="queued",
        config=EvaluationConfiguration(
            name="queued",
            eval_type=EvaluationType.SINGLE,
            profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
            metrics=("accuracy",),
        ),
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
    )
    run.queue()
    run.collect_events()
    return run


class TestCreateHandlerCapturesExecutionInputs:
    """Create handler persists the request's execution inputs in config."""

    async def test_create_handler_stores_dataset_items_in_config(self) -> None:
        repo = AsyncMock()
        repo.save = AsyncMock()
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_name="create-capture",
            provider="openai",
            model="gpt-4",
            metrics=("accuracy",),
            prompt_template=PROMPT_TEMPLATE,
            dataset_items=DATASET_ITEMS,
        )

        result = await handler.handle(command)

        assert result.config.dataset_items == DATASET_ITEMS
        assert result.config.prompt_template == PROMPT_TEMPLATE

    async def test_create_handler_stores_prompt_template_in_config(self) -> None:
        repo = AsyncMock()
        repo.save = AsyncMock()
        handler = CreateEvaluationRunHandler(repo)
        command = CreateEvaluationRunCommand(
            evaluation_name="create-capture",
            provider="openai",
            model="gpt-4",
            metrics=("accuracy",),
            prompt_template=PROMPT_TEMPLATE,
        )

        result = await handler.handle(command)

        assert result.config.prompt_template == PROMPT_TEMPLATE


class TestRetryHandlerCopiesExecutionInputs:
    """Retry handler reproduces the source run's execution inputs."""

    async def test_retry_handler_copies_dataset_items(self) -> None:
        source = _make_source_run()
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=source)
        repo.save = AsyncMock()
        handler = RetryEvaluationRunHandler(repo)

        result = await handler.handle(RetryEvaluationRunCommand(run_id=str(source.id)))

        assert result.id != source.id
        assert result.config.dataset_items == DATASET_ITEMS

    async def test_retry_handler_copies_prompt_template(self) -> None:
        source = _make_source_run()
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=source)
        repo.save = AsyncMock()
        handler = RetryEvaluationRunHandler(repo)

        result = await handler.handle(RetryEvaluationRunCommand(run_id=str(source.id)))

        assert result.config.prompt_template == PROMPT_TEMPLATE

    async def test_retry_handler_does_not_mutate_source(self) -> None:
        source = _make_source_run()
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=source)
        repo.save = AsyncMock()
        handler = RetryEvaluationRunHandler(repo)

        await handler.handle(RetryEvaluationRunCommand(run_id=str(source.id)))

        assert source.config.dataset_items == DATASET_ITEMS
        assert source.config.prompt_template == PROMPT_TEMPLATE


class TestCreateEndpointSchedulesSameInputs:
    """Create endpoint schedules a workflow with the request's execution inputs."""

    async def test_create_workflow_input_carries_request_inputs(self) -> None:
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_repo = AsyncMock()
        mock_repo.save = AsyncMock()
        mock_repo.find_by_workflow_id = AsyncMock(return_value=None)

        queue_instance = AsyncMock()
        queue_instance.handle = AsyncMock(return_value=_make_queued_run())

        captured_inputs: list[Any] = []

        async def _capture(workflow: Any, input_data: Any, **kwargs: Any) -> None:
            captured_inputs.append(input_data)

        mock_tc = MagicMock()
        mock_tc.start_workflow = _capture
        mock_config = MagicMock()
        mock_config.temporal_task_queue = "redops-eval"

        body = CreateEvaluationRunRequest(
            evaluation_name="create-inputs",
            provider="openai",
            model="gpt-4",
            metrics=["accuracy"],
            system_prompt="sys-prompt",
            prompt_template=PROMPT_TEMPLATE,
            dataset_items=[
                DatasetItemRequest(prompt="q1", context="c1"),
                DatasetItemRequest(prompt="q2"),
            ],
        )

        with (
            patch("app.api.evaluation_run._get_repository", return_value=mock_repo),
            patch("app.api.evaluation_run.QueueEvaluationRunHandler", return_value=queue_instance),
            patch("app.api.evaluation_run._run_to_response", return_value=MagicMock()),
        ):
            from app.api.evaluation_run import create_run

            await create_run(
                body,
                request=MagicMock(headers={}),
                current_user=MagicMock(user_id="test-user"),
                session=mock_session,
                temporal_client=mock_tc,
                config=mock_config,
            )

        assert len(captured_inputs) == 1
        inp = captured_inputs[0]
        assert inp.provider_name == "openai"
        assert inp.model_id == "gpt-4"
        assert inp.metric_names == ("accuracy",)
        assert inp.system_prompt == "sys-prompt"
        assert inp.prompt_template == PROMPT_TEMPLATE
        assert inp.dataset_items == (
            {"prompt": "q1", "context": "c1"},
            {"prompt": "q2"},
        )
