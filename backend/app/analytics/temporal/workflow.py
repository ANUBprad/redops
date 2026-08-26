"""Temporal workflow for report generation and export.

Orchestrates the full report generation and export pipeline inside
Temporal, avoiding HTTP timeouts for large exports.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from temporalio.common import RetryPolicy

    from app.analytics.temporal.activities import (
        ExportResult,
        GenerateExportInput,
        generate_export_activity,
    )


@workflow.defn
class ExportReportWorkflow:
    """Workflow that generates and exports a report.

    Delegates to a single activity call with a generous timeout.
    Retry is limited to avoid duplicating expensive report generation work.
    """

    @workflow.run
    async def run(
        self,
        input: GenerateExportInput,
    ) -> ExportResult:
        """Execute the report export workflow."""
        activity_retry = RetryPolicy(
            maximum_attempts=2,
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            non_retryable_error_types=["ValueError", "KeyError"],
        )

        result: ExportResult = await workflow.execute_activity(
            generate_export_activity,
            GenerateExportInput(
                report_type=input.report_type,
                project_id=input.project_id,
                evaluation_id=input.evaluation_id,
                run_id=input.run_id,
                days=input.days,
                export_format=input.export_format,
                generated_by=input.generated_by,
            ),
            start_to_close_timeout=timedelta(minutes=15),
            schedule_to_close_timeout=timedelta(minutes=20),
            retry_policy=activity_retry,
        )

        return result
