"""Pydantic schemas for replay API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MetricExplanationResponse(BaseModel):
    """Response model for a metric explanation."""

    metric_name: str = Field(..., description="Metric identifier")
    score: float = Field(..., description="Raw metric score")
    normalized_score: float = Field(..., description="Normalized score [0.0, 1.0]")
    confidence: float = Field(..., description="Judge confidence")
    reasoning: str = Field(default="", description="Judge reasoning")
    explanation: str = Field(default="", description="Human-readable explanation")
    version: str = Field(default="1.0.0", description="Metric version")
    judge_model: str = Field(default="", description="Judge model used")


class ItemReportResponse(BaseModel):
    """Response model for an item replay report."""

    item_index: int = Field(..., description="Item index in the dataset")
    prompt_preview: str = Field(default="", description="First 200 chars of prompt")
    provider_response_preview: str = Field(default="", description="First 200 chars of response")
    provider_error: str | None = Field(default=None, description="Provider error if any")
    metric_explanations: list[MetricExplanationResponse] = Field(default_factory=list)
    total_latency_ms: int = Field(default=0, description="Total item latency")
    total_cost_usd: float = Field(default=0.0, description="Total item cost")
    error: str | None = Field(default=None, description="Item error if any")


class MetricSummaryResponse(BaseModel):
    """Response model for a metric summary."""

    metric_name: str = Field(..., description="Metric identifier")
    mean: float = Field(..., description="Mean score across items")
    min_score: float = Field(..., description="Minimum score")
    max_score: float = Field(..., description="Maximum score")
    count: int = Field(..., description="Number of items")


class ReplaySummaryResponse(BaseModel):
    """Response model for replay summary."""

    run_id: str = Field(..., description="Run ID")
    evaluation_name: str = Field(default="", description="Evaluation name")
    provider: str = Field(default="", description="Provider name")
    model: str = Field(default="", description="Model ID")
    status: str = Field(..., description="Run status")
    total_items: int = Field(..., description="Total items")
    successful_items: int = Field(..., description="Successful items")
    failed_items: int = Field(..., description="Failed items")
    total_cost_usd: float = Field(..., description="Total cost")
    total_tokens_input: int = Field(..., description="Total input tokens")
    total_tokens_output: int = Field(..., description="Total output tokens")
    total_latency_ms: int = Field(..., description="Total latency")
    metric_summaries: dict[str, MetricSummaryResponse] = Field(default_factory=dict)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)


class TimelineEntryResponse(BaseModel):
    """Response model for a timeline entry."""

    timestamp: datetime
    event_type: str
    sequence: int
    duration_ms: int = 0
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ReplayReportResponse(BaseModel):
    """Full replay report response."""

    summary: ReplaySummaryResponse
    item_reports: list[ItemReportResponse] = Field(default_factory=list)
    timeline: list[TimelineEntryResponse] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)


class ItemComparisonResponse(BaseModel):
    """Response model for item comparison."""

    item_index: int
    metric_deltas: dict[str, dict[str, float]] = Field(default_factory=dict)
    latency_delta: int = 0
    cost_delta: float = 0.0


class TraceComparisonResponse(BaseModel):
    """Response model for trace comparison."""

    baseline_run_id: str
    comparison_run_id: str
    baseline_provider: str
    comparison_provider: str
    baseline_model: str
    comparison_model: str
    metric_deltas: dict[str, dict[str, float]] = Field(default_factory=dict)
    cost_delta: float = 0.0
    latency_delta: int = 0
    item_comparisons: list[ItemComparisonResponse] = Field(default_factory=list)
    winner: str = Field(default="tie", description="Winner of comparison")
    confidence: float = Field(default=0.0, description="Comparison confidence")
