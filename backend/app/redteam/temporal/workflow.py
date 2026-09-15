"""Temporal workflow for red team campaign execution.

Orchestrates a single red team campaign activity with appropriate
timeouts and retry policies.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from temporalio.common import RetryPolicy

    from app.redteam.temporal.activities import (
        RedTeamWorkflowInput,
        RedTeamWorkflowResult,
        red_team_campaign_activity,
    )


@workflow.defn
class RedTeamWorkflow:
    """Workflow that runs a red team campaign to completion.

    Delegates the full campaign loop to a single activity call
    with a generous timeout. Supports cooperative cancellation via
    the ``cancel`` signal, which triggers ``TRY_CANCEL`` on the
    activity handle.
    """

    def __init__(self) -> None:
        self._cancelled: bool = False
        self._activity_handle: workflow.ActivityHandle[RedTeamWorkflowResult] | None = None

    @workflow.signal
    def cancel(self) -> None:
        self._cancelled = True
        if self._activity_handle is not None and not self._activity_handle.done():
            self._activity_handle.cancel()

    @workflow.run
    async def run(
        self,
        input: RedTeamWorkflowInput,
    ) -> RedTeamWorkflowResult:
        """Execute the red team campaign workflow."""
        if self._cancelled:
            return RedTeamWorkflowResult(
                attack_run_id=input.attack_run_id,
                status="cancelled",
            )

        activity_retry = RetryPolicy(
            maximum_attempts=2,
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            non_retryable_error_types=["ValueError", "KeyError"],
        )

        self._activity_handle = workflow.start_activity(
            red_team_campaign_activity,
            RedTeamWorkflowInput(
                attack_run_id=input.attack_run_id,
                target_provider=input.target_provider,
                target_model=input.target_model,
                target_temperature=input.target_temperature,
                target_max_tokens=input.target_max_tokens,
                attack_categories=input.attack_categories,
                max_rounds=input.max_rounds,
                max_attacks=input.max_attacks,
                max_total_tokens=input.max_total_tokens,
                max_cost_usd=input.max_cost_usd,
                max_duration_seconds=input.max_duration_seconds,
                effectiveness_threshold=input.effectiveness_threshold,
            ),
            start_to_close_timeout=timedelta(hours=2),
            schedule_to_close_timeout=timedelta(hours=2, minutes=15),
            retry_policy=activity_retry,
            cancellation_type=workflow.ActivityCancellationType.TRY_CANCEL,
        )

        try:
            await self._activity_handle
        except ActivityError:
            if self._cancelled:
                return RedTeamWorkflowResult(
                    attack_run_id=input.attack_run_id,
                    status="cancelled",
                )
            raise

        campaign_result = self._activity_handle.result()
        return campaign_result
