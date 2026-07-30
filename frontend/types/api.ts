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
