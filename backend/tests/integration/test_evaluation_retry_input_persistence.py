"""P3-4 tests: retry execution inputs are persisted and reproduced.

Proves the failure mode end to end against the real data layer:

1-6.  run config serialization stores dataset_items and prompt_template
7-9.  legacy (pre-persistence) rows deserialize safely and stay non-replayable
15-18. a real SQLAlchemy persistence round trip reproduces the SAME dataset
       items and prompt template on the retry run
19-22. a real legacy row refuses retry (ConflictError) and no second run
       is ever created, so no evaluation can be fabricated from it
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.evaluation.application.run_commands import (
    CreateEvaluationRunCommand,
    RetryEvaluationRunCommand,
)
from app.evaluation.application.run_handlers import (
    CreateEvaluationRunHandler,
    RetryEvaluationRunHandler,
)
from app.evaluation.domain.enums.evaluation_enums import EvaluationType
from app.evaluation.domain.value_objects.evaluation_value_objects import (
    EvaluationConfiguration,
    EvaluationProfile,
)
from app.infrastructure.database.models.base import Base
from app.infrastructure.database.models.evaluation_run import EvaluationRunModel
from app.infrastructure.database.repositories.evaluation_run_repository import (
    SqlAlchemyEvaluationRunRepository,
    _deserialize_config,
    _serialize_config,
)
from app.kernel.entities.base import UUIDv7
from app.kernel.exceptions.errors import ConflictError

PROMPT_TEMPLATE = "Answer using only the context.\n{context}\nQuestion: {prompt}"
DATASET_ITEMS = (
    {"prompt": "What is the capital of France?", "context": "Paris is the capital."},
    {"prompt": "What is 2 + 2?", "context": "Two plus two is four."},
)


def _make_config(
    *,
    dataset_items: tuple[dict[str, str], ...] = DATASET_ITEMS,
    prompt_template: str | None = PROMPT_TEMPLATE,
) -> EvaluationConfiguration:
    """Build a configuration carrying real execution inputs."""
    return EvaluationConfiguration(
        name="persisted-run",
        eval_type=EvaluationType.SINGLE,
        profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
        metrics=("accuracy", "faithfulness"),
        prompt_template=prompt_template,
        dataset_items=dataset_items,
    )


class TestConfigSerialization:
    """dataset_items and prompt_template round trip through the JSON config."""

    def test_serialize_config_stores_dataset_items(self) -> None:
        serialized = _serialize_config(_make_config())

        assert serialized["dataset_items"] == list(DATASET_ITEMS)

    def test_serialize_config_stores_prompt_template(self) -> None:
        serialized = _serialize_config(_make_config())

        assert serialized["prompt_template"] == PROMPT_TEMPLATE

    def test_serialize_empty_dataset_items_produces_empty_list(self) -> None:
        serialized = _serialize_config(_make_config(dataset_items=()))

        assert serialized["dataset_items"] == []

    def test_deserialize_config_restores_dataset_items(self) -> None:
        restored = _deserialize_config(_serialize_config(_make_config()))

        assert restored.dataset_items == DATASET_ITEMS
        assert restored.prompt_template == PROMPT_TEMPLATE

    def test_round_trip_preserves_full_config(self) -> None:
        config = _make_config()

        restored = _deserialize_config(_serialize_config(config))

        assert restored == config
        assert restored.name == config.name
        assert restored.eval_type == config.eval_type
        assert restored.profile == config.profile
        assert restored.metrics == config.metrics
        assert restored.budget == config.budget
        assert restored.limits == config.limits
        assert restored.policy == config.policy
        assert restored.priority == config.priority

    def test_legacy_config_without_input_keys_deserializes_safely(self) -> None:
        legacy = _serialize_config(_make_config())
        legacy.pop("prompt_template")
        legacy.pop("dataset_items")

        restored = _deserialize_config(legacy)

        assert restored.prompt_template is None
        assert restored.dataset_items == ()

    def test_legacy_config_with_null_input_keys_deserializes_safely(self) -> None:
        legacy = _serialize_config(_make_config())
        legacy["prompt_template"] = None
        legacy["dataset_items"] = None

        restored = _deserialize_config(legacy)

        assert restored.prompt_template is None
        assert restored.dataset_items == ()

    def test_malformed_dataset_items_entries_are_dropped(self) -> None:
        serialized = _serialize_config(_make_config())
        serialized["dataset_items"] = [{"prompt": "ok"}, None, "garbage", 42]

        restored = _deserialize_config(serialized)

        assert restored.dataset_items == ({"prompt": "ok"},)


class TestRealPersistenceRetryFidelity:
    """A failed run created through the real repository retries with the SAME inputs."""

    async def test_retry_reproduces_same_dataset_after_persistence(self) -> None:
        engine = create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, ([EvaluationRunModel.__table__]))
        factory: Any = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as session:
            repo = SqlAlchemyEvaluationRunRepository(session)
            create_handler = CreateEvaluationRunHandler(repo)
            command = CreateEvaluationRunCommand(
                evaluation_id="e2e-evaluation",
                evaluation_name="persist-and-retry",
                provider="deterministic-test",
                model="gpt-4o",
                metrics=("accuracy",),
                prompt_template=PROMPT_TEMPLATE,
                dataset_items=DATASET_ITEMS,
            )
            created = await create_handler.handle(command)
            created.queue()
            created.start(total_items=len(DATASET_ITEMS))
            created.fail(error_code="ALL_ITEMS_FAILED", error_message="boom")
            created.collect_events()
            await repo.save(created)
            await session.commit()

        async with factory() as session:
            repo = SqlAlchemyEvaluationRunRepository(session)
            source = await repo.find_by_id(UUIDv7.from_string(str(created.id)))
            assert source is not None
            retry_handler = RetryEvaluationRunHandler(repo)
            new_run = await retry_handler.handle(RetryEvaluationRunCommand(run_id=str(source.id)))
            await session.commit()

            assert new_run.id != source.id
            assert new_run.status.value == "created"
            assert new_run.config.dataset_items == DATASET_ITEMS
            assert new_run.config.prompt_template == PROMPT_TEMPLATE

        async with factory() as session:
            repo = SqlAlchemyEvaluationRunRepository(session)
            persisted = await repo.find_by_id(UUIDv7.from_string(str(new_run.id)))
            assert persisted is not None
            assert persisted.config.dataset_items == DATASET_ITEMS
            assert persisted.config.prompt_template == PROMPT_TEMPLATE

    async def test_legacy_persisted_row_refuses_retry_and_creates_nothing(self) -> None:
        engine = create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, ([EvaluationRunModel.__table__]))
        factory: Any = async_sessionmaker(engine, expire_on_commit=False)

        legacy_config = _serialize_config(
            EvaluationConfiguration(
                name="legacy-run",
                eval_type=EvaluationType.SINGLE,
                profile=EvaluationProfile(provider_name="openai", model_id="gpt-4"),
                metrics=("accuracy",),
            )
        )
        legacy_config.pop("prompt_template")
        legacy_config.pop("dataset_items")

        async with factory() as session:
            legacy_id = str(UUIDv7())
            session.add(
                EvaluationRunModel(
                    id=legacy_id,
                    evaluation_name="legacy-fixture",
                    provider="openai",
                    model="gpt-4",
                    status="failed",
                    items_total=2,
                    items_failed=2,
                    config=legacy_config,
                    profile={
                        "provider_name": "openai",
                        "model_id": "gpt-4",
                        "temperature": 0.0,
                        "max_tokens": 4096,
                        "timeout_seconds": 60,
                        "system_prompt": None,
                    },
                    metadata_={},
                )
            )
            await session.commit()

        async with factory() as session:
            repo = SqlAlchemyEvaluationRunRepository(session)
            source = await repo.find_by_id(UUIDv7.from_string(legacy_id))
            assert source is not None

            retry_handler = RetryEvaluationRunHandler(repo)
            with pytest.raises(ConflictError, match="dataset inputs were not persisted"):
                await retry_handler.handle(RetryEvaluationRunCommand(run_id=legacy_id))

        async with factory() as session:
            rows = await session.scalars(
                select(EvaluationRunModel).where(
                    EvaluationRunModel.evaluation_name == "legacy-fixture"
                )
            )
            assert len(list(rows)) == 1
