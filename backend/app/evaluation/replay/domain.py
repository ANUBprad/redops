"""Domain model for execution traces.

Captures the complete lifecycle of an evaluation run for replay,
debugging, and analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from typing import Any


@unique
class TraceEventType(Enum):
    """Types of events captured in an execution trace."""

    RUN_CREATED = "run_created"
    RUN_QUEUED = "run_queued"
    RUN_STARTED = "run_started"
    ITEM_STARTED = "item_started"
    PROVIDER_REQUEST = "provider_request"
    PROVIDER_RESPONSE = "provider_response"
    METRIC_STARTED = "metric_started"
    METRIC_COMPLETED = "metric_completed"
    ITEM_COMPLETED = "item_completed"
    ITEM_FAILED = "item_failed"
    AGGREGATION_COMPLETED = "aggregation_completed"
    PERSISTENCE_COMPLETED = "persistence_completed"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    CHECKPOINT_CREATED = "checkpoint_created"
    JUDGE_REQUEST = "judge_request"
    JUDGE_RESPONSE = "judge_response"


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """A single event in an execution trace."""

    event_type: TraceEventType
    timestamp: datetime
    sequence: int
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PromptTrace:
    """Trace of a prompt through the system."""

    prompt: str
    context: str = ""
    reference: str = ""
    retrieved_documents: tuple[str, ...] = ()
    tool_calls: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderTrace:
    """Trace of a provider invocation."""

    provider_name: str
    model_id: str
    request_messages: tuple[dict[str, Any], ...] = ()
    request_options: dict[str, Any] = field(default_factory=dict)
    response_content: str = ""
    response_tool_calls: tuple[dict[str, Any], ...] = ()
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = ""
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MetricTrace:
    """Trace of a metric evaluation."""

    metric_name: str
    score: float
    normalized_score: float
    confidence: float = 0.0
    reasoning: str = ""
    version: str = "1.0.0"
    cost_usd: float = 0.0
    execution_time_ms: int = 0
    judge_model: str = ""
    judge_prompt_version: str = ""
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ItemTrace:
    """Complete trace for a single evaluation item."""

    item_index: int
    prompt_trace: PromptTrace
    provider_trace: ProviderTrace | None = None
    metric_traces: tuple[MetricTrace, ...] = ()
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionTrace:
    """Complete execution trace for an evaluation run.

    Captures every event, prompt, provider call, metric evaluation,
    and result for full replay and debugging capability.
    """

    run_id: str
    evaluation_name: str = ""
    provider_name: str = ""
    model_id: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: str = "created"
    events: tuple[TraceEvent, ...] = ()
    item_traces: tuple[ItemTrace, ...] = ()
    aggregated_metrics: dict[str, dict[str, float]] = field(default_factory=dict)
    configuration: dict[str, Any] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_latency_ms: int = 0
    error: str | None = None

    @property
    def duration_ms(self) -> int:
        """Total execution duration in milliseconds."""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return self.total_latency_ms

    @property
    def item_count(self) -> int:
        """Number of items traced."""
        return len(self.item_traces)

    @property
    def success_count(self) -> int:
        """Number of items that completed without error."""
        return sum(1 for it in self.item_traces if it.error is None)

    @property
    def failure_count(self) -> int:
        """Number of items that failed."""
        return sum(1 for it in self.item_traces if it.error is not None)

    def get_item(self, index: int) -> ItemTrace | None:
        """Get trace for a specific item by index."""
        for it in self.item_traces:
            if it.item_index == index:
                return it
        return None

    def get_events_by_type(self, event_type: TraceEventType) -> list[TraceEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def to_dict(self) -> dict[str, Any]:
        """Serialize trace to dictionary for storage."""
        return {
            "run_id": self.run_id,
            "evaluation_name": self.evaluation_name,
            "provider_name": self.provider_name,
            "model_id": self.model_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "events": [
                {
                    "event_type": e.event_type.value,
                    "timestamp": e.timestamp.isoformat(),
                    "sequence": e.sequence,
                    "data": e.data,
                    "duration_ms": e.duration_ms,
                    "error": e.error,
                }
                for e in self.events
            ],
            "item_traces": [
                {
                    "item_index": it.item_index,
                    "prompt_trace": {
                        "prompt": it.prompt_trace.prompt,
                        "context": it.prompt_trace.context,
                        "reference": it.prompt_trace.reference,
                        "retrieved_documents": list(it.prompt_trace.retrieved_documents),
                        "tool_calls": list(it.prompt_trace.tool_calls),
                    },
                    "provider_trace": {
                        "provider_name": it.provider_trace.provider_name,
                        "model_id": it.provider_trace.model_id,
                        "request_messages": list(it.provider_trace.request_messages),
                        "request_options": it.provider_trace.request_options,
                        "response_content": it.provider_trace.response_content,
                        "tokens_input": it.provider_trace.tokens_input,
                        "tokens_output": it.provider_trace.tokens_output,
                        "cost_usd": it.provider_trace.cost_usd,
                        "latency_ms": it.provider_trace.latency_ms,
                        "error": it.provider_trace.error,
                    }
                    if it.provider_trace
                    else None,
                    "metric_traces": [
                        {
                            "metric_name": mt.metric_name,
                            "score": mt.score,
                            "normalized_score": mt.normalized_score,
                            "confidence": mt.confidence,
                            "reasoning": mt.reasoning,
                            "version": mt.version,
                            "cost_usd": mt.cost_usd,
                            "execution_time_ms": mt.execution_time_ms,
                            "judge_model": mt.judge_model,
                            "error": mt.error,
                        }
                        for mt in it.metric_traces
                    ],
                    "total_latency_ms": it.total_latency_ms,
                    "total_cost_usd": it.total_cost_usd,
                    "error": it.error,
                }
                for it in self.item_traces
            ],
            "aggregated_metrics": self.aggregated_metrics,
            "configuration": self.configuration,
            "total_cost_usd": self.total_cost_usd,
            "total_tokens_input": self.total_tokens_input,
            "total_tokens_output": self.total_tokens_output,
            "total_latency_ms": self.total_latency_ms,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionTrace:
        """Deserialize trace from dictionary."""
        from datetime import datetime as dt

        events = tuple(
            TraceEvent(
                event_type=TraceEventType(e["event_type"]),
                timestamp=dt.fromisoformat(e["timestamp"]),
                sequence=e["sequence"],
                data=e.get("data", {}),
                duration_ms=e.get("duration_ms", 0),
                error=e.get("error"),
            )
            for e in data.get("events", [])
        )

        item_traces = tuple(
            ItemTrace(
                item_index=it["item_index"],
                prompt_trace=PromptTrace(
                    prompt=it["prompt_trace"]["prompt"],
                    context=it["prompt_trace"].get("context", ""),
                    reference=it["prompt_trace"].get("reference", ""),
                    retrieved_documents=tuple(it["prompt_trace"].get("retrieved_documents", [])),
                    tool_calls=tuple(it["prompt_trace"].get("tool_calls", [])),
                ),
                provider_trace=ProviderTrace(
                    provider_name=it["provider_trace"]["provider_name"],
                    model_id=it["provider_trace"]["model_id"],
                    request_messages=tuple(it["provider_trace"].get("request_messages", [])),
                    request_options=it["provider_trace"].get("request_options", {}),
                    response_content=it["provider_trace"].get("response_content", ""),
                    tokens_input=it["provider_trace"].get("tokens_input", 0),
                    tokens_output=it["provider_trace"].get("tokens_output", 0),
                    cost_usd=it["provider_trace"].get("cost_usd", 0.0),
                    latency_ms=it["provider_trace"].get("latency_ms", 0),
                    error=it["provider_trace"].get("error"),
                )
                if it.get("provider_trace")
                else None,
                metric_traces=tuple(
                    MetricTrace(
                        metric_name=mt["metric_name"],
                        score=mt["score"],
                        normalized_score=mt["normalized_score"],
                        confidence=mt.get("confidence", 0.0),
                        reasoning=mt.get("reasoning", ""),
                        version=mt.get("version", "1.0.0"),
                        cost_usd=mt.get("cost_usd", 0.0),
                        execution_time_ms=mt.get("execution_time_ms", 0),
                        judge_model=mt.get("judge_model", ""),
                        error=mt.get("error"),
                    )
                    for mt in it.get("metric_traces", [])
                ),
                total_latency_ms=it.get("total_latency_ms", 0),
                total_cost_usd=it.get("total_cost_usd", 0.0),
                error=it.get("error"),
            )
            for it in data.get("item_traces", [])
        )

        return cls(
            run_id=data["run_id"],
            evaluation_name=data.get("evaluation_name", ""),
            provider_name=data.get("provider_name", ""),
            model_id=data.get("model_id", ""),
            started_at=dt.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=dt.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
            status=data.get("status", "created"),
            events=events,
            item_traces=item_traces,
            aggregated_metrics=data.get("aggregated_metrics", {}),
            configuration=data.get("configuration", {}),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            total_tokens_input=data.get("total_tokens_input", 0),
            total_tokens_output=data.get("total_tokens_output", 0),
            total_latency_ms=data.get("total_latency_ms", 0),
            error=data.get("error"),
        )
