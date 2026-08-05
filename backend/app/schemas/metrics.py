"""Pydantic schemas for metrics API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreItemRequest(BaseModel):
    """Request body for scoring a single item."""

    run_id: str = Field(..., description="Evaluation run ID")
    item_id: str = Field(..., description="Evaluation item ID")
    prompt: str = Field(default="", description="The prompt sent to the model")
    response: str = Field(default="", description="The model response")
    reference: str = Field(default="", description="Reference/expected answer")
    context: str = Field(default="", description="Context for RAG evaluation")
    tool_calls: list[dict[str, object]] = Field(
        default_factory=list,
        description="Tool calls in the response",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Additional metadata (latency_ms, cost_usd, etc.)",
    )
    metric_names: list[str] = Field(
        default_factory=list,
        description="Specific metrics to evaluate (empty = all)",
    )


class ScoreBatchRequest(BaseModel):
    """Request body for scoring multiple items."""

    items: list[ScoreItemRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Items to score",
    )


class MetricResultResponse(BaseModel):
    """Response model for a single metric result."""

    metric_name: str = Field(..., description="Metric identifier")
    score: float = Field(..., description="Raw metric score")
    normalized_score: float = Field(..., description="Normalized score [0.0, 1.0]")
    raw_output: str = Field(default="", description="Raw metric output")
    reasoning: str = Field(default="", description="Explanation of the score")
    metadata: dict[str, object] = Field(default_factory=dict)
    execution_time_ms: int = Field(default=0, description="Execution time in ms")
    error: str | None = Field(default=None, description="Error message if failed")
    confidence: float = Field(default=0.0, description="Judge confidence [0.0, 1.0]")
    version: str = Field(default="1.0.0", description="Metric version")
    cost_usd: float = Field(default=0.0, description="Cost in USD for this evaluation")


class MetricAggregationResponse(BaseModel):
    """Response model for aggregated metric scores."""

    metric_name: str = Field(..., description="Metric identifier")
    mean: float = Field(..., description="Mean score")
    median: float = Field(..., description="Median score")
    std_dev: float = Field(..., description="Standard deviation")
    min_score: float = Field(..., description="Minimum score")
    max_score: float = Field(..., description="Maximum score")
    item_count: int = Field(..., description="Total items evaluated")
    success_count: int = Field(..., description="Successfully evaluated items")
    error_count: int = Field(..., description="Items with errors")
    success_rate: float = Field(..., description="Success rate [0.0, 1.0]")


class MetricDefinitionResponse(BaseModel):
    """Response model for a metric definition."""

    name: str = Field(..., description="Metric identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this metric measures")
    category: str = Field(..., description="Metric category")
    scale: str = Field(..., description="Score scale type")
    version: str = Field(..., description="Metric version")
    requires_context: bool = Field(default=False)
    default_weight: float = Field(default=1.0)
    tags: list[str] = Field(default_factory=list)


class MetricResultsListResponse(BaseModel):
    """Paginated list of metric results."""

    items: list[MetricResultResponse] = Field(default_factory=list)
    total: int = Field(..., description="Total matching results")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total pages")


class AggregatedScoresResponse(BaseModel):
    """Aggregated scores for all metrics in a run."""

    run_id: str = Field(..., description="Evaluation run ID")
    aggregations: list[MetricAggregationResponse] = Field(default_factory=list)


class ConfigureEvaluationMetricsRequest(BaseModel):
    """Request body for enabling/disabling metrics on an evaluation."""

    metric_names: list[str] = Field(
        ...,
        min_length=0,
        description="Full list of enabled metric names",
    )
