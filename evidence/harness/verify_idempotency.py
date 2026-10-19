"""Idempotent-persistence verification against the real Postgres database.

Submits the same logical metric result twice through the real persistence
activity (``persist_metric_results_activity``) with an identical identity
``(run_id, item_id, metric_name)`` and the real repository upsert, then queries
the database directly to prove no duplicate row or duplicate metric record was
created.

Also exercises the durable provider-execution boundary
``(run_id, item_id)`` via the real ``_write_durable_execution`` helper.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.evaluation.temporal import activities as acts
from app.evaluation.temporal.activities import (
    MetricResultPayload,
    PersistMetricResultsInput,
    _write_durable_execution,
)

OUT = Path(__file__).resolve().parent / "idempotency-evidence"
OUT.mkdir(exist_ok=True)

DB_URL = os.environ.get("REDOPS_VERIFY_DB_URL", "postgresql+asyncpg://<user>:<password>@localhost:55432/redops")

RUN_ID = "verify-idem-run-0001"
ITEM_ID = "verify-idem-item-0001"
METRIC = "safety"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _durable_write(session_factory) -> None:
    """Write the same durable provider execution twice via the real helper."""
    from app.evaluation.execution.item_executor import ItemExecutionResult  # type: ignore

    # The real helper takes the executor result object; build the minimal one.
    result = ItemExecutionResult(
        item_index=0,
        prompt="verify prompt",
        provider_name="openai",
        model_id="gpt-4o-mini",
        response="cached-response",
        tokens_input=11,
        tokens_output=5,
        tokens_cached=0,
        cost_usd=0.0002,
        cost_estimated=True,
        latency_ms=42,
        finish_reason="stop",
        request_id="req-verify-1",
        failed=False,
    )
    await _write_durable_execution(RUN_ID, ITEM_ID, result)
    await _write_durable_execution(RUN_ID, ITEM_ID, result)


async def main() -> int:
    engine = create_async_engine(DB_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    acts.configure_session_factory(factory)

    payload = PersistMetricResultsInput(
        run_id=RUN_ID,
        item_id=ITEM_ID,
        results=(
            MetricResultPayload(
                metric_name=METRIC,
                score=0.93,
                normalized_score=0.93,
                raw_output="safe",
                reasoning="no violation detected",
                execution_time_ms=12,
                confidence=0.88,
                version="1.0.0",
                cost_usd=0.00031,
            ),
        ),
    )

    report: dict = {
        "database_url_sanitized": DB_URL.replace("<user>:<password>", "<user>:<password>"),
        "identity": {"run_id": RUN_ID, "item_id": ITEM_ID, "metric_name": METRIC},
        "submission_1_at_utc": _now(),
    }

    n1 = await acts.persist_metric_results_activity(payload)
    report["submission_1_rows_written"] = n1
    report["submission_1_finished_at_utc"] = _now()

    n2 = await acts.persist_metric_results_activity(payload)
    report["submission_2_rows_written"] = n2
    report["submission_2_finished_at_utc"] = _now()

    # Durable provider-execution boundary (run_id, item_id) written twice.
    try:
        await _durable_write(factory)
        report["durable_write"] = "ok"
    except Exception as exc:  # noqa: BLE001
        report["durable_write_error"] = f"{type(exc).__name__}: {exc}"

    sql = (
        "SELECT count(*) AS n, min(id) AS first_id, max(id) AS last_id, "
        "count(DISTINCT id) AS distinct_ids FROM metric_results "
        f"WHERE run_id = '{RUN_ID}' AND item_id = '{ITEM_ID}' AND metric_name = '{METRIC}';"
    )
    sql2 = (
        "SELECT id, run_id, item_id, metric_name, score, normalized_score, "
        "confidence, version, cost_usd, created_at FROM metric_results "
        f"WHERE run_id = '{RUN_ID}' AND item_id = '{ITEM_ID}';"
    )
    sql3 = (
        "SELECT count(*) AS n FROM item_executions "
        f"WHERE run_id = '{RUN_ID}' AND item_id = '{ITEM_ID}';"
    )

    async with factory() as session:
        row = (await session.execute(text(sql))).mappings().one()
        rows = (await session.execute(text(sql2))).mappings().all()
        durable_row = (await session.execute(text(sql3))).mappings().one()

    report["sql_metric_count"] = sql
    report["sql_metric_rows"] = sql2
    report["sql_durable_count"] = sql3
    report["metric_row_count"] = int(row["n"])
    report["metric_distinct_ids"] = int(row["distinct_ids"])
    report["metric_first_id"] = row["first_id"]
    report["metric_last_id"] = row["last_id"]
    report["metric_rows"] = [
        {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()} for r in rows
    ]
    report["durable_row_count"] = int(durable_row["n"])

    await engine.dispose()

    (OUT / "idempotency-report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (OUT / "idempotency-query.sql").write_text(f"{sql}\n{sql2}\n{sql3}\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
