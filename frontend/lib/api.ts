import { type PaginatedResponse, type UUID } from "@/types/api";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = await response.text();
    }
    const detail =
      typeof errorData === "object" && errorData !== null && "detail" in errorData
        ? String((errorData as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(detail, response.status, errorData);
  }

  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Health
  health: () => request<{ status: string; version: string; service: string }>("/health"),
  readiness: () => request<{ status: string; version: string; service: string; checks: unknown[] }>("/ready"),

  // Evaluations
  listEvaluations: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/evaluations${query}`);
  },
  getEvaluation: (id: UUID) => request<unknown>(`/evaluations/${id}`),
  createEvaluation: (data: Record<string, unknown>) => request<unknown>("/evaluations", { method: "POST", body: JSON.stringify(data) }),
  updateEvaluation: (id: UUID, data: Record<string, unknown>) => request<unknown>(`/evaluations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteEvaluation: (id: UUID) => request<void>(`/evaluations/${id}`, { method: "DELETE" }),
  duplicateEvaluation: (id: UUID, data: { name: string }) => request<unknown>(`/evaluations/${id}/duplicate`, { method: "POST", body: JSON.stringify(data) }),
  archiveEvaluation: (id: UUID) => request<unknown>(`/evaluations/${id}/archive`, { method: "POST" }),
  markReady: (id: UUID) => request<unknown>(`/evaluations/${id}/ready`, { method: "POST" }),

  // Runs
  listRuns: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/runs${query}`);
  },
  getRun: (id: UUID) => request<unknown>(`/runs/${id}`),
  createRun: (data: Record<string, unknown>) => request<unknown>("/runs", { method: "POST", body: JSON.stringify(data) }),
  cancelRun: (id: UUID, data: { reason?: string; force?: boolean }) => request<unknown>(`/runs/${id}/cancel`, { method: "POST", body: JSON.stringify(data) }),
  retryRun: (id: UUID) => request<unknown>(`/runs/${id}/retry`, { method: "POST" }),
  listRunsForEvaluation: (evaluationId: UUID, params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/runs/evaluation/${evaluationId}${query}`);
  },

  // Observability
  getTimeline: (runId: UUID, params?: { event_type?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.event_type) qs.set("event_type", params.event_type);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ items: unknown[]; total: number }>(`/runs/${runId}/events${query}`);
  },
  getLogs: (runId: UUID, params?: { level?: string; source?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.level) qs.set("level", params.level);
    if (params?.source) qs.set("source", params.source);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ items: unknown[]; total: number }>(`/runs/${runId}/logs${query}`);
  },
  createLog: (runId: UUID, data: { level: string; source: string; message: string; metadata?: Record<string, unknown>; correlation_id?: string }) =>
    request<unknown>(`/runs/${runId}/logs`, { method: "POST", body: JSON.stringify(data) }),

  // SSE streams
  streamEvents: (runId: UUID): EventSource => {
    const url = `${BASE_URL.replace("/api/v1", "")}/runs/${runId}/events/stream`;
    return new EventSource(url);
  },
  streamProgress: (runId: UUID): EventSource => {
    const url = `${BASE_URL.replace("/api/v1", "")}/runs/${runId}/progress/stream`;
    return new EventSource(url);
  },

  // Metrics
  listMetrics: (category?: string) => {
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    return request<unknown[]>(`/metrics${query}`);
  },
  scoreItem: (data: Record<string, unknown>) => request<unknown[]>("/metrics/score", { method: "POST", body: JSON.stringify(data) }),
  getMetricResults: (runId: UUID, metricName?: string) => {
    const query = metricName ? `?metric_name=${encodeURIComponent(metricName)}` : "";
    return request<{ items: unknown[]; total: number; page: number; page_size: number; total_pages: number }>(`/metrics/runs/${runId}/results${query}`);
  },
  getAggregatedScores: (runId: UUID, metricName?: string) => {
    const query = metricName ? `?metric_name=${encodeURIComponent(metricName)}` : "";
    return request<{ run_id: UUID; aggregations: unknown[] }>(`/metrics/runs/${runId}/scores${query}`);
  },

  // Agents
  listAgents: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/agents${query}`);
  },
  getAgent: (id: UUID) => request<unknown>(`/agents/${id}`),
  createAgent: (data: Record<string, unknown>) => request<unknown>("/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: UUID, data: Record<string, unknown>) => request<unknown>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAgent: (id: UUID) => request<void>(`/agents/${id}`, { method: "DELETE" }),
  activateAgent: (id: UUID) => request<unknown>(`/agents/${id}/activate`, { method: "POST" }),
  deactivateAgent: (id: UUID) => request<unknown>(`/agents/${id}/deactivate`, { method: "POST" }),
  archiveAgent: (id: UUID) => request<unknown>(`/agents/${id}/archive`, { method: "POST" }),

  // Red Team - Attack Definitions
  listAttackDefinitions: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/redteam/definitions${query}`);
  },
  getAttackDefinition: (id: UUID) => request<unknown>(`/redteam/definitions/${id}`),
  createAttackDefinition: (data: Record<string, unknown>) => request<unknown>("/redteam/definitions", { method: "POST", body: JSON.stringify(data) }),
  updateAttackDefinition: (id: UUID, data: Record<string, unknown>) => request<unknown>(`/redteam/definitions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAttackDefinition: (id: UUID) => request<void>(`/redteam/definitions/${id}`, { method: "DELETE" }),
  activateAttackDefinition: (id: UUID) => request<unknown>(`/redteam/definitions/${id}/activate`, { method: "POST" }),
  archiveAttackDefinition: (id: UUID) => request<unknown>(`/redteam/definitions/${id}/archive`, { method: "POST" }),

  // Red Team - Attack Runs
  listAttackRuns: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/redteam/runs${query}`);
  },
  getAttackRun: (id: UUID) => request<unknown>(`/redteam/runs/${id}`),
  createAttackRun: (data: Record<string, unknown>) => request<unknown>("/redteam/runs", { method: "POST", body: JSON.stringify(data) }),
  startAttackRun: (id: UUID, data: { total_items: number }) => request<unknown>(`/redteam/runs/${id}/start`, { method: "POST", body: JSON.stringify(data) }),
  completeAttackRun: (id: UUID) => request<unknown>(`/redteam/runs/${id}/complete`, { method: "POST" }),
  failAttackRun: (id: UUID, data: { error_message?: string }) => request<unknown>(`/redteam/runs/${id}/fail`, { method: "POST", body: JSON.stringify(data) }),
  cancelAttackRun: (id: UUID) => request<unknown>(`/redteam/runs/${id}/cancel`, { method: "POST" }),

  // Analytics
  getDashboardSummary: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/dashboard${query}`);
  },
  getHistoricalTrends: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/trends${query}`);
  },
  getCostAnalysis: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/cost${query}`);
  },
  getLatencyAnalysis: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/latency${query}`);
  },
  getSafetyTrend: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/safety${query}`);
  },
  getLeaderboard: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/leaderboard${query}`);
  },
  getComparison: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/comparison${query}`);
  },
  generateReport: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/reports/generate${query}`);
  },
};
