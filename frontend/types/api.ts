/**
 * Type definitions for the RedOps Eval API.
 * Mirrors the Pydantic schemas from the backend.
 */

export type UUID = string;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export type EvaluationStatus = "draft" | "active" | "archived" | "ready";

export interface EvaluationDefinition {
  id: UUID;
  project_id: string;
  dataset_id: string | null;
  name: string;
  description: string | null;
  provider: string;
  model: string;
  metrics: string[];
  tags: string[];
  configuration: Record<string, unknown>;
  status: EvaluationStatus;
  created_by: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface EvaluationSummary {
  id: UUID;
  project_id: string;
  name: string;
  provider: string;
  model: string;
  status: EvaluationStatus;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export type RunStatus =
  | "created"
  | "queued"
  | "starting"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "paused"
  | "cancelling"
  | "timed_out";

export interface EvaluationRun {
  id: UUID;
  evaluation_id: string | null;
  evaluation_name: string;
  workflow_id: string | null;
  provider: string;
  model: string;
  status: RunStatus;
  priority: string;
  items_total: number;
  items_completed: number;
  items_failed: number;
  progress: number;
  token_input: number;
  token_output: number;
  total_tokens: number;
  cost: number;
  average_latency_ms: number;
  failure_reason: string | null;
  version: number;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RunSummary {
  id: UUID;
  evaluation_id: string | null;
  evaluation_name: string;
  provider: string;
  model: string;
  status: RunStatus;
  progress: number;
  items_total: number;
  items_completed: number;
  items_failed: number;
  cost: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface TimelineEvent {
  event_id: UUID;
  run_id: UUID;
  event_type: string;
  data: Record<string, unknown>;
  correlation_id: string | null;
  occurred_at: string;
}

export interface LogEntry {
  log_id: UUID;
  run_id: UUID;
  level: "DEBUG" | "INFO" | "WARN" | "ERROR";
  source: string;
  message: string;
  metadata: Record<string, unknown>;
  correlation_id: string | null;
  timestamp: string;
}

export interface MetricResult {
  metric_name: string;
  score: number;
  normalized_score: number;
  raw_output: string;
  reasoning: string;
  metadata: Record<string, unknown>;
  execution_time_ms: number;
  error: string | null;
}

export interface MetricAggregation {
  metric_name: string;
  mean: number;
  median: number;
  std_dev: number;
  min_score: number;
  max_score: number;
  item_count: number;
  success_count: number;
  error_count: number;
  success_rate: number;
}

export interface MetricDefinition {
  name: string;
  display_name: string;
  description: string;
  category: string;
  scale: string;
  version: string;
  requires_context: boolean;
  default_weight: number;
  tags: string[];
}

export type AttackCategory =
  | "prompt_injection"
  | "jailbreak"
  | "system_prompt_extraction"
  | "role_manipulation"
  | "context_poisoning"
  | "instruction_override"
  | "tool_misuse"
  | "sensitive_data_extraction"
  | "policy_circumvention"
  | "output_format_manipulation";

export type AttackSeverity = "low" | "medium" | "high" | "critical";
export type AttackDefinitionStatus = "draft" | "active" | "archived";
export type AttackStatus = "created" | "queued" | "starting" | "running" | "completed" | "failed" | "cancelled";
export type SafetyVerdict = "safe" | "suspicious" | "violated" | "leaked" | "error";
export type SafetyDimension =
  | "harmlessness"
  | "policy_compliance"
  | "prompt_integrity"
  | "data_confidentiality"
  | "tool_governance"
  | "output_fidelity";

export interface AttackDefinition {
  id: UUID;
  name: string;
  description: string;
  category: AttackCategory;
  severity: AttackSeverity;
  status: AttackDefinitionStatus;
  prompt_template: string;
  system_prompt_override: string | null;
  expected_behavior: string;
  parameters: Record<string, unknown>;
  tags: string[];
  created_by: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AttackRun {
  id: UUID;
  evaluation_run_id: string | null;
  status: AttackStatus;
  attack_definition_ids: UUID[];
  configuration: Record<string, unknown>;
  items_total: number;
  items_completed: number;
  items_passed: number;
  items_violated: number;
  items_failed: number;
  progress: number;
  version: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SafetyScore {
  dimension: SafetyDimension;
  score: number;
  normalized_score: number;
  verdict: SafetyVerdict;
  reasoning: string;
  confidence: number;
}

export interface Project {
  id: UUID;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Analytics Types ────────────────────────────────────────────

export interface ActivityEntry {
  id: string;
  type: string;
  name: string;
  status: string;
  timestamp: string | null;
  summary: string;
}

export interface DashboardSummary {
  total_evaluations: number;
  completed_runs: number;
  success_rate: number;
  average_score: number;
  average_latency_ms: number;
  average_cost: number;
  total_token_usage: number;
  average_safety_score: number;
  attack_success_rate: number;
  recent_activity: ActivityEntry[];
}

export interface TrendPoint {
  timestamp: string;
  value: number;
  label: string;
}

export interface TrendSeries {
  name: string;
  points: TrendPoint[];
  direction: "up" | "down" | "flat";
  change_percent: number;
}

export interface ProviderCost {
  provider: string;
  total_cost: number;
  run_count: number;
  average_cost_per_run: number;
}

export interface ModelCost {
  model: string;
  provider: string;
  total_cost: number;
  run_count: number;
  average_cost_per_run: number;
}

export interface CostAnalysis {
  total_cost: number;
  average_cost_per_run: number;
  average_cost_per_item: number;
  cost_by_provider: ProviderCost[];
  cost_by_model: ModelCost[];
  projected_monthly_cost: number;
}

export interface ProviderLatency {
  provider: string;
  average_latency_ms: number;
  run_count: number;
}

export interface ModelLatency {
  model: string;
  provider: string;
  average_latency_ms: number;
  run_count: number;
}

export interface LatencyAnalysis {
  average_latency_ms: number;
  median_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  min_latency_ms: number;
  max_latency_ms: number;
  latency_by_provider: ProviderLatency[];
  latency_by_model: ModelLatency[];
}

export interface DimensionScore {
  dimension: string;
  score: number;
  verdict: string;
  sample_count: number;
}

export interface SafetyTrend {
  average_safety_score: number;
  violation_rate: number;
  pass_rate: number;
  safety_by_dimension: DimensionScore[];
  total_attacks: number;
  total_violations: number;
}

export interface LeaderboardEntry {
  rank: number;
  entity_id: string;
  entity_name: string;
  entity_type: string;
  score: number;
  metric_name: string;
  metadata: Record<string, string>;
}

export interface Leaderboard {
  title: string;
  ranking_by: string;
  entries: LeaderboardEntry[];
  generated_at: string | null;
}

export interface ComparedItem {
  entity_id: string;
  entity_name: string;
  entity_type: string;
}

export interface MetricValue {
  entity_id: string;
  value: number;
  formatted_value: string;
}

export interface ComparisonMetric {
  metric_name: string;
  values: MetricValue[];
  best_entity_id: string;
}

export interface ComparisonResult {
  title: string;
  compared_items: ComparedItem[];
  metrics: ComparisonMetric[];
  summary: string;
}

export interface ReportSection {
  title: string;
  content: string;
  statistics: Record<string, number>;
}

export interface GeneratedReport {
  id: string;
  report_type: string;
  title: string;
  description: string;
  generated_at: string | null;
  summary: string;
  recommendations: string[];
  statistics: Record<string, number>;
  sections: ReportSection[];
}

// ─── Phase 7: Enterprise Platform Types ────────────────────────

export interface Organization {
  id: UUID;
  name: string;
  slug: string;
  description: string | null;
  owner_id: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Membership {
  id: UUID;
  user_id: string;
  organization_id: string;
  role: string;
  invited_by: string | null;
  is_active: boolean;
  joined_at: string;
  created_at: string;
}

export interface Invitation {
  id: UUID;
  email: string;
  organization_id: string;
  role: string;
  invited_by: string;
  status: string;
  expires_at: string;
  created_at: string;
}

export interface Project {
  id: UUID;
  name: string;
  description: string | null;
  organization_id: string;
  created_by: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyInfo {
  id: UUID;
  name: string;
  prefix: string;
  user_id: string;
  organization_id: string | null;
  scopes: string[];
  expires_at: string | null;
  last_used_at: string | null;
  usage_count: number;
  is_active: boolean;
  rotated_from: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleInfo {
  id: UUID;
  name: string;
  schedule_type: string;
  cron_expression: string;
  task_config: Record<string, unknown>;
  organization_id: string | null;
  project_id: string | null;
  created_by: string | null;
  timezone: string;
  status: string;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  failure_count: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AuditLogEntry {
  log_id: UUID;
  user_id: string;
  user_email: string;
  action: string;
  resource_type: string;
  resource_id: string;
  organization_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  metadata: Record<string, unknown>;
  timestamp: string;
  request_id: string | null;
}

export interface NotificationEntry {
  notification_id: UUID;
  organization_id: string;
  user_id: string;
  channel: string;
  event: string;
  title: string;
  message: string;
  metadata: Record<string, unknown>;
  status: string;
  target: string;
  error_message: string | null;
  retry_count: number;
  timestamp: string;
}

// ─── Agent Run Types ─────────────────────────────────────────

export type AgentRunStatus =
  | "created"
  | "queued"
  | "starting"
  | "running"
  | "paused"
  | "cancelling"
  | "completed"
  | "failed"
  | "timedout"
  | "cancelled";

export type AgentRunPriority = "low" | "normal" | "high" | "critical";

export interface AgentRunSummary {
  id: UUID;
  agent_definition_id: string | null;
  agent_name: string;
  provider: string;
  model: string;
  status: AgentRunStatus;
  progress: number;
  steps_total: number;
  steps_completed: number;
  steps_failed: number;
  cost: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface AgentRunDetail {
  id: UUID;
  agent_definition_id: string | null;
  agent_name: string;
  workflow_id: string | null;
  provider: string;
  model: string;
  status: AgentRunStatus;
  priority: AgentRunPriority;
  steps_total: number;
  steps_completed: number;
  steps_failed: number;
  progress: number;
  token_input: number;
  token_output: number;
  total_tokens: number;
  cost: number;
  average_latency_ms: number;
  failure_reason: string | null;
  version: number;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAgentRunPayload {
  agent_name: string;
  agent_definition_id?: string;
  provider: string;
  model: string;
  tools?: string[];
  max_steps?: number;
  timeout_seconds?: number;
  project_id?: string;
  tags?: string[];
}
