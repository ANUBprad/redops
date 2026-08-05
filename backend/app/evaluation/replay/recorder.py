"""Trace recorder for capturing execution events.

Records all events during an evaluation run for replay and analysis.
Thread-safe via asyncio lock for concurrent item execution.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.evaluation.replay.domain import (
    ExecutionTrace,
    ItemTrace,
    MetricTrace,
    PromptTrace,
    ProviderTrace,
    TraceEvent,
    TraceEventType,
)

logger = logging.getLogger(__name__)


class TraceRecorder:
    """Records execution events for replay.

    Captures provider calls, metric evaluations, and lifecycle events
    during an evaluation run. Thread-safe for concurrent item execution.
    """

    def __init__(self, run_id: str, evaluation_name: str = "") -> None:
        self._run_id = run_id
        self._evaluation_name = evaluation_name
        self._events: list[TraceEvent] = []
        self._item_traces: dict[int, _ItemTraceBuilder] = {}
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._status = "created"
        self._provider_name = ""
        self._model_id = ""
        self._configuration: dict[str, Any] = {}
        self._aggregated_metrics: dict[str, dict[str, float]] = {}
        self._total_cost_usd = 0.0
        self._total_tokens_input = 0
        self._total_tokens_output = 0
        self._total_latency_ms = 0
        self._error: str | None = None

    def set_configuration(self, config: dict[str, Any]) -> None:
        """Set the run configuration for the trace."""
        self._configuration = config

    def set_provider(self, provider_name: str, model_id: str) -> None:
        """Set the provider and model for the trace."""
        self._provider_name = provider_name
        self._model_id = model_id

    async def record_event(
        self,
        event_type: TraceEventType,
        data: dict[str, Any] | None = None,
        duration_ms: int = 0,
        error: str | None = None,
    ) -> None:
        """Record a lifecycle event."""
        async with self._lock:
            self._sequence += 1
            event = TraceEvent(
                event_type=event_type,
                timestamp=datetime.now(UTC),
                sequence=self._sequence,
                data=data or {},
                duration_ms=duration_ms,
                error=error,
            )
            self._events.append(event)

            if event_type == TraceEventType.RUN_STARTED:
                self._started_at = event.timestamp
                self._status = "running"
            elif event_type == TraceEventType.RUN_COMPLETED:
                self._completed_at = event.timestamp
                self._status = "completed"
            elif event_type == TraceEventType.RUN_FAILED:
                self._completed_at = event.timestamp
                self._status = "failed"
                self._error = error
            elif event_type == TraceEventType.RUN_CANCELLED:
                self._completed_at = event.timestamp
                self._status = "cancelled"

    async def record_prompt(
        self,
        item_index: int,
        prompt: str,
        context: str = "",
        reference: str = "",
        retrieved_documents: tuple[str, ...] = (),
        tool_calls: tuple[dict[str, Any], ...] = (),
    ) -> None:
        """Record prompt details for an item."""
        async with self._lock:
            builder = self._get_or_create_item(item_index)
            builder.prompt_trace = PromptTrace(
                prompt=prompt,
                context=context,
                reference=reference,
                retrieved_documents=retrieved_documents,
                tool_calls=tool_calls,
            )

    async def record_provider_request(
        self,
        item_index: int,
        provider_name: str,
        model_id: str,
        messages: tuple[dict[str, Any], ...] = (),
        options: dict[str, Any] | None = None,
    ) -> None:
        """Record a provider request."""
        async with self._lock:
            builder = self._get_or_create_item(item_index)
            builder.provider_trace = ProviderTrace(
                provider_name=provider_name,
                model_id=model_id,
                request_messages=messages,
                request_options=options or {},
            )

    async def record_provider_response(
        self,
        item_index: int,
        content: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
        latency_ms: int = 0,
        finish_reason: str = "",
        tool_calls: tuple[dict[str, Any], ...] = (),
        error: str | None = None,
    ) -> None:
        """Record a provider response."""
        async with self._lock:
            builder = self._get_or_create_item(item_index)
            existing = builder.provider_trace
            if existing:
                builder.provider_trace = ProviderTrace(
                    provider_name=existing.provider_name,
                    model_id=existing.model_id,
                    request_messages=existing.request_messages,
                    request_options=existing.request_options,
                    response_content=content,
                    response_tool_calls=tool_calls,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    finish_reason=finish_reason,
                    error=error,
                )
            else:
                builder.provider_trace = ProviderTrace(
                    provider_name=self._provider_name,
                    model_id=self._model_id,
                    response_content=content,
                    tokens_input=tokens_input,
                    tokens_output=tokens_output,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    finish_reason=finish_reason,
                    error=error,
                )

            self._total_cost_usd += cost_usd
            self._total_tokens_input += tokens_input
            self._total_tokens_output += tokens_output
            self._total_latency_ms += latency_ms

    async def record_metric(
        self,
        item_index: int,
        metric_name: str,
        score: float,
        normalized_score: float,
        confidence: float = 0.0,
        reasoning: str = "",
        version: str = "1.0.0",
        cost_usd: float = 0.0,
        execution_time_ms: int = 0,
        judge_model: str = "",
        judge_prompt_version: str = "",
        error: str | None = None,
    ) -> None:
        """Record a metric evaluation result."""
        async with self._lock:
            builder = self._get_or_create_item(item_index)
            builder.metric_traces.append(
                MetricTrace(
                    metric_name=metric_name,
                    score=score,
                    normalized_score=normalized_score,
                    confidence=confidence,
                    reasoning=reasoning,
                    version=version,
                    cost_usd=cost_usd,
                    execution_time_ms=execution_time_ms,
                    judge_model=judge_model,
                    judge_prompt_version=judge_prompt_version,
                    error=error,
                )
            )

    async def record_item_error(self, item_index: int, error: str) -> None:
        """Record an item-level error."""
        async with self._lock:
            builder = self._get_or_create_item(item_index)
            builder.error = error

    def _get_or_create_item(self, index: int) -> _ItemTraceBuilder:
        """Get or create an item trace builder."""
        if index not in self._item_traces:
            self._item_traces[index] = _ItemTraceBuilder(item_index=index)
        return self._item_traces[index]

    def build_trace(self) -> ExecutionTrace:
        """Build the final execution trace."""
        item_traces = tuple(
            builder.to_item_trace()
            for builder in sorted(
                self._item_traces.values(),
                key=lambda b: b.item_index,
            )
        )

        return ExecutionTrace(
            run_id=self._run_id,
            evaluation_name=self._evaluation_name,
            provider_name=self._provider_name,
            model_id=self._model_id,
            started_at=self._started_at,
            completed_at=self._completed_at,
            status=self._status,
            events=tuple(self._events),
            item_traces=item_traces,
            aggregated_metrics=self._aggregated_metrics,
            configuration=self._configuration,
            total_cost_usd=self._total_cost_usd,
            total_tokens_input=self._total_tokens_input,
            total_tokens_output=self._total_tokens_output,
            total_latency_ms=self._total_latency_ms,
            error=self._error,
        )


class _ItemTraceBuilder:
    """Mutable builder for a single item trace."""

    def __init__(self, item_index: int) -> None:
        self.item_index = item_index
        self.prompt_trace = PromptTrace(prompt="")
        self.provider_trace: ProviderTrace | None = None
        self.metric_traces: list[MetricTrace] = []
        self.total_latency_ms = 0
        self.total_cost_usd = 0.0
        self.error: str | None = None

    def to_item_trace(self) -> ItemTrace:
        """Build the immutable ItemTrace."""
        return ItemTrace(
            item_index=self.item_index,
            prompt_trace=self.prompt_trace,
            provider_trace=self.provider_trace,
            metric_traces=tuple(self.metric_traces),
            total_latency_ms=self.total_latency_ms,
            total_cost_usd=self.total_cost_usd,
            error=self.error,
        )
