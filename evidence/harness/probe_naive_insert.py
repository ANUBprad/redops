"""Pre-fix probe: does the real durable item-execution write work on Postgres?

Confirms whether the naive-DateTime ORM models break a second, independent
Postgres persistence path (item_executions) the same way metric_results does.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.evaluation.temporal import activities as acts
from app.evaluation.execution.item_executor import ItemExecutionResult

DB_URL = os.environ.get("REDOPS_VERIFY_DB_URL", "postgresql+asyncpg://<user>:<password>@localhost:55432/redops")


async def main() -> int:
    engine = create_async_engine(DB_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    acts.configure_session_factory(factory)
    result = ItemExecutionResult(
        item_index=0,
        prompt="probe",
        provider_name="openai",
        model_id="gpt-4o-mini",
        response="probe-response",
        tokens_input=3,
        tokens_output=2,
        tokens_cached=0,
        cost_usd=0.0001,
        cost_estimated=True,
        latency_ms=9,
        finish_reason="stop",
        request_id="probe-req-1",
        failed=False,
    )
    try:
        await acts._write_durable_execution("probe-run-0001", "probe-item-0001", result)
        print("item_executions write: OK")
    except Exception as exc:  # noqa: BLE001
        print(f"item_executions write: ERR {type(exc).__name__}: {exc}")
    await engine.dispose()
    return 0


raise SystemExit(asyncio.run(main()))
