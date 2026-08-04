"""Analytics API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    """Response model for dashboard summary."""

    total_evaluations: int = 0
    completed_runs: int = 0
    success_rate: float = 0.0
    average_score: float = 0.0
    average_latency_ms: float = 0.0
    average_cost: float = 0.0
    total_token_usage: int = 0
    average_safety_score: float = 0.0
    attack_success_rate: float = 0.0
    recent_activity: list[ActivityEntryResponse] = Field(default_factory=list)


class ActivityEntryResponse(BaseModel):
    """Activity entry response."""

    id: str = ""
    type: str = ""
    name: str = ""
    status: str = ""
    timestamp: str | None = None
    summary: str = ""


DashboardSummaryResponse.model_rebuild()


class TrendPointResponse(BaseModel):
    """Trend point response."""

    timestamp: str
    value: float
    label: str = ""


class TrendSeriesResponse(BaseModel):
    """Trend series response."""

    name: str
    points: list[TrendPointResponse] = Field(default_factory=list)
    direction: str = "flat"
    change_percent: float = 0.0


class CostAnalysisResponse(BaseModel):
    """Cost analysis response."""

    total_cost: float = 0.0
    average_cost_per_run: float = 0.0
    average_cost_per_item: float = 0.0
    cost_by_provider: list[ProviderCostResponse] = Field(default_factory=list)
    cost_by_model: list[ModelCostResponse] = Field(default_factory=list)
    projected_monthly_cost: float = 0.0


class ProviderCostResponse(BaseModel):
    """Provider cost response."""

    provider: str = ""
    total_cost: float = 0.0
    run_count: int = 0
    average_cost_per_run: float = 0.0


class ModelCostResponse(BaseModel):
    """Model cost response."""

    model: str = ""
    provider: str = ""
    total_cost: float = 0.0
    run_count: int = 0
    average_cost_per_run: float = 0.0


CostAnalysisResponse.model_rebuild()


class LatencyAnalysisResponse(BaseModel):
    """Latency analysis response."""

    average_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    latency_by_provider: list[ProviderLatencyResponse] = Field(default_factory=list)
    latency_by_model: list[ModelLatencyResponse] = Field(default_factory=list)


class ProviderLatencyResponse(BaseModel):
    """Provider latency response."""

    provider: str = ""
    average_latency_ms: float = 0.0
    run_count: int = 0


class ModelLatencyResponse(BaseModel):
    """Model latency response."""

    model: str = ""
    provider: str = ""
    average_latency_ms: float = 0.0
    run_count: int = 0


class SafetyTrendResponse(BaseModel):
    """Safety trend response."""

    average_safety_score: float = 0.0
    violation_rate: float = 0.0
    pass_rate: float = 0.0
    safety_by_dimension: list[DimensionScoreResponse] = Field(default_factory=list)
    total_attacks: int = 0
    total_violations: int = 0


class DimensionScoreResponse(BaseModel):
    """Dimension score response."""

    dimension: str = ""
    score: float = 0.0
    verdict: str = ""
    sample_count: int = 0


class LeaderboardResponse(BaseModel):
    """Leaderboard response."""

    title: str = ""
    ranking_by: str = ""
    entries: list[LeaderboardEntryResponse] = Field(default_factory=list)
    generated_at: str | None = None


class LeaderboardEntryResponse(BaseModel):
    """Leaderboard entry response."""

    rank: int = 0
    entity_id: str = ""
    entity_name: str = ""
    entity_type: str = ""
    score: float = 0.0
    metric_name: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class ComparisonResultResponse(BaseModel):
    """Comparison result response."""

    title: str = ""
    compared_items: list[ComparedItemResponse] = Field(default_factory=list)
    metrics: list[ComparisonMetricResponse] = Field(default_factory=list)
    summary: str = ""


class ComparedItemResponse(BaseModel):
    """Compared item response."""

    entity_id: str = ""
    entity_name: str = ""
    entity_type: str = ""


class ComparisonMetricResponse(BaseModel):
    """Comparison metric response."""

    metric_name: str = ""
    values: list[MetricValueResponse] = Field(default_factory=list)
    best_entity_id: str = ""


class MetricValueResponse(BaseModel):
    """Metric value response."""

    entity_id: str = ""
    value: float = 0.0
    formatted_value: str = ""


class GeneratedReportResponse(BaseModel):
    """Generated report response."""

    id: str = ""
    report_type: str = ""
    title: str = ""
    description: str = ""
    generated_at: str | None = None
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)
    statistics: dict[str, float] = Field(default_factory=dict)
    sections: list[ReportSectionResponse] = Field(default_factory=list)


class ReportSectionResponse(BaseModel):
    """Report section response."""

    title: str = ""
    content: str = ""
    statistics: dict[str, float] = Field(default_factory=dict)
