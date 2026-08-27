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

  const token = localStorage.getItem("redops-access-token");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

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

class AuthenticatedEventSource implements EventSource {
  private controller: AbortController;
  private _onmessage: ((event: MessageEvent) => void) | null = null;
  private _onerror: ((event: Event) => void) | null = null;
  private _onopen: ((event: Event) => void) | null = null;
  readyState: number = 0;
  url: string;
  withCredentials: boolean = false;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;

  constructor(url: string) {
    this.url = url;
    this.controller = new AbortController();
    this.readyState = 0;
    this.connect();
  }

  private async connect(): Promise<void> {
    const headers: Record<string, string> = {};
    const token = localStorage.getItem("redops-access-token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    try {
      const response = await fetch(this.url, {
        headers,
        signal: this.controller.signal,
      });

      if (!response.ok) {
        this.readyState = 2;
        this._onerror?.(new Event("error"));
        return;
      }

      this.readyState = 1;
      this._onopen?.(new Event("open"));

      const reader = response.body?.getReader();
      if (!reader) {
        this.readyState = 2;
        this._onerror?.(new Event("error"));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            this._onmessage?.({ data } as MessageEvent);
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      this._onerror?.(new Event("error"));
    } finally {
      this.readyState = 2;
    }
  }

  get onmessage(): ((event: MessageEvent) => void) | null {
    return this._onmessage;
  }

  set onmessage(handler: ((event: MessageEvent) => void) | null) {
    this._onmessage = handler;
  }

  get onerror(): ((event: Event) => void) | null {
    return this._onerror;
  }

  set onerror(handler: ((event: Event) => void) | null) {
    this._onerror = handler;
  }

  get onopen(): ((event: Event) => void) | null {
    return this._onopen;
  }

  set onopen(handler: ((event: Event) => void) | null) {
    this._onopen = handler;
  }

  close(): void {
    this.readyState = 2;
    this.controller.abort();
  }

  addEventListener(): void {}
  removeEventListener(): void {}
  dispatchEvent(): boolean {
    return true;
  }
}

function createAuthenticatedEventSource(url: string): EventSource {
  return new AuthenticatedEventSource(url);
}

export const api = {
  // Health
  health: () => request<{ status: string; version: string; service: string }>("/health"),
  readiness: () =>
    request<{ status: string; version: string; service: string; checks: unknown[] }>("/ready"),

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
  createEvaluation: (data: Record<string, unknown>) =>
    request<unknown>("/evaluations", { method: "POST", body: JSON.stringify(data) }),
  updateEvaluation: (id: UUID, data: Record<string, unknown>) =>
    request<unknown>(`/evaluations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteEvaluation: (id: UUID) => request<void>(`/evaluations/${id}`, { method: "DELETE" }),
  duplicateEvaluation: (id: UUID, data: { name: string }) =>
    request<unknown>(`/evaluations/${id}/duplicate`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  archiveEvaluation: (id: UUID) =>
    request<unknown>(`/evaluations/${id}/archive`, { method: "POST" }),
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
  createRun: (data: Record<string, unknown>) =>
    request<unknown>("/runs", { method: "POST", body: JSON.stringify(data) }),
  cancelRun: (id: UUID, data: { reason?: string; force?: boolean }) =>
    request<unknown>(`/runs/${id}/cancel`, { method: "POST", body: JSON.stringify(data) }),
  retryRun: (id: UUID) => request<unknown>(`/runs/${id}/retry`, { method: "POST" }),
  listRunsForEvaluation: (
    evaluationId: UUID,
    params: Record<string, string | number | undefined>,
  ) => {
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
  getLogs: (
    runId: UUID,
    params?: { level?: string; source?: string; limit?: number; offset?: number },
  ) => {
    const qs = new URLSearchParams();
    if (params?.level) qs.set("level", params.level);
    if (params?.source) qs.set("source", params.source);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ items: unknown[]; total: number }>(`/runs/${runId}/logs${query}`);
  },
  createLog: (
    runId: UUID,
    data: {
      level: string;
      source: string;
      message: string;
      metadata?: Record<string, unknown>;
      correlation_id?: string;
    },
  ) => request<unknown>(`/runs/${runId}/logs`, { method: "POST", body: JSON.stringify(data) }),

  // SSE streams
  streamEvents: (runId: UUID): EventSource => {
    const url = `${BASE_URL}/runs/${runId}/events/stream`;
    return createAuthenticatedEventSource(url);
  },
  streamProgress: (runId: UUID): EventSource => {
    const url = `${BASE_URL}/runs/${runId}/progress/stream`;
    return createAuthenticatedEventSource(url);
  },

  // Replay
  getTrace: (runId: UUID) => request<unknown>(`/replay/traces/${runId}`),
  getReplayReport: (runId: UUID) => request<unknown>(`/replay/traces/${runId}/report`),
  compareRuns: (baselineRunId: UUID, comparisonRunId: UUID) =>
    request<unknown>(`/replay/compare/${baselineRunId}/${comparisonRunId}`),
  analyzeRegression: (baselineRunId: UUID, currentRunId: UUID) =>
    request<unknown>(`/replay/regression/${baselineRunId}/${currentRunId}`),

  // Metrics
  listMetrics: (category?: string) => {
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    return request<unknown[]>(`/metrics${query}`);
  },
  scoreItem: (data: Record<string, unknown>) =>
    request<unknown[]>("/metrics/score", { method: "POST", body: JSON.stringify(data) }),
  getMetricResults: (runId: UUID, metricName?: string) => {
    const query = metricName ? `?metric_name=${encodeURIComponent(metricName)}` : "";
    return request<{
      items: unknown[];
      total: number;
      page: number;
      page_size: number;
      total_pages: number;
    }>(`/metrics/runs/${runId}/results${query}`);
  },
  getAggregatedScores: (runId: UUID, metricName?: string) => {
    const query = metricName ? `?metric_name=${encodeURIComponent(metricName)}` : "";
    return request<{ run_id: UUID; aggregations: unknown[] }>(
      `/metrics/runs/${runId}/scores${query}`,
    );
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
  createAgent: (data: Record<string, unknown>) =>
    request<unknown>("/agents", { method: "POST", body: JSON.stringify(data) }),
  updateAgent: (id: UUID, data: Record<string, unknown>) =>
    request<unknown>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAgent: (id: UUID) => request<void>(`/agents/${id}`, { method: "DELETE" }),
  activateAgent: (id: UUID) => request<unknown>(`/agents/${id}/activate`, { method: "POST" }),
  deactivateAgent: (id: UUID) => request<unknown>(`/agents/${id}/deactivate`, { method: "POST" }),
  archiveAgent: (id: UUID) => request<unknown>(`/agents/${id}/archive`, { method: "POST" }),

  // Agent Runs
  listAgentRuns: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/agent-runs${query}`);
  },
  getAgentRun: (id: UUID) => request<unknown>(`/agent-runs/${id}`),
  createAgentRun: (data: Record<string, unknown>) =>
    request<unknown>("/agent-runs", { method: "POST", body: JSON.stringify(data) }),
  cancelAgentRun: (id: UUID, data: { reason?: string; force?: boolean }) =>
    request<unknown>(`/agent-runs/${id}/cancel`, { method: "POST", body: JSON.stringify(data) }),
  retryAgentRun: (id: UUID) => request<unknown>(`/agent-runs/${id}/retry`, { method: "POST" }),

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
  createAttackDefinition: (data: Record<string, unknown>) =>
    request<unknown>("/redteam/definitions", { method: "POST", body: JSON.stringify(data) }),
  updateAttackDefinition: (id: UUID, data: Record<string, unknown>) =>
    request<unknown>(`/redteam/definitions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteAttackDefinition: (id: UUID) =>
    request<void>(`/redteam/definitions/${id}`, { method: "DELETE" }),
  activateAttackDefinition: (id: UUID) =>
    request<unknown>(`/redteam/definitions/${id}/activate`, { method: "POST" }),
  archiveAttackDefinition: (id: UUID) =>
    request<unknown>(`/redteam/definitions/${id}/archive`, { method: "POST" }),

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
  createAttackRun: (data: Record<string, unknown>) =>
    request<unknown>("/redteam/runs", { method: "POST", body: JSON.stringify(data) }),
  startAttackRun: (id: UUID, data: { total_items: number }) =>
    request<unknown>(`/redteam/runs/${id}/start`, { method: "POST", body: JSON.stringify(data) }),
  completeAttackRun: (id: UUID) =>
    request<unknown>(`/redteam/runs/${id}/complete`, { method: "POST" }),
  failAttackRun: (id: UUID, data: { error_message?: string }) =>
    request<unknown>(`/redteam/runs/${id}/fail`, { method: "POST", body: JSON.stringify(data) }),
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

  // ─── Auth ────────────────────────────────────────────────────
  login: (data: { email: string; password: string }) =>
    request<{ access_token: string; refresh_token: string; expires_in: number }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  register: (data: { email: string; display_name: string; password: string }) =>
    request<{ access_token: string; refresh_token: string; expires_in: number }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getMe: () => request<unknown>("/auth/me"),
  refreshToken: (data: { refresh_token: string }) =>
    request<{ access_token: string; refresh_token: string; expires_in: number }>(
      "/auth/refresh",
      { method: "POST", body: JSON.stringify(data) },
    ),
  logout: () => request<void>("/auth/logout", { method: "POST" }),

  // ─── Experiments ─────────────────────────────────────────────
  listExperiments: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/experiments${query}`);
  },
  getExperiment: (id: UUID) => request<unknown>(`/experiments/${id}`),
  createExperiment: (data: Record<string, unknown>) =>
    request<unknown>("/experiments", { method: "POST", body: JSON.stringify(data) }),
  updateExperiment: (id: UUID, data: Record<string, unknown>) =>
    request<unknown>(`/experiments/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteExperiment: (id: UUID) => request<void>(`/experiments/${id}`, { method: "DELETE" }),
  archiveExperiment: (id: UUID) =>
    request<unknown>(`/experiments/${id}/archive`, { method: "POST" }),

  // ─── Profiles ────────────────────────────────────────────────
  listProfiles: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/profiles${query}`);
  },
  getProfile: (id: UUID) => request<unknown>(`/profiles/${id}`),
  createProfile: (data: Record<string, unknown>) =>
    request<unknown>("/profiles", { method: "POST", body: JSON.stringify(data) }),
  updateProfile: (id: UUID, data: Record<string, unknown>) =>
    request<unknown>(`/profiles/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteProfile: (id: UUID) => request<void>(`/profiles/${id}`, { method: "DELETE" }),
  getDefaultProfile: (category: string) =>
    request<unknown>(`/profiles/default?category=${encodeURIComponent(category)}`),

  // ─── Datasets ────────────────────────────────────────────────
  listDatasets: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/datasets${query}`);
  },
  getDataset: (id: UUID) => request<unknown>(`/datasets/${id}`),
  createDataset: (data: { name: string; description?: string; items: unknown[] }) =>
    request<unknown>("/datasets", { method: "POST", body: JSON.stringify(data) }),
  uploadDatasetItems: (id: UUID, items: unknown[]) =>
    request<unknown>(`/datasets/${id}/items`, { method: "POST", body: JSON.stringify({ items }) }),
  deleteDataset: (id: UUID) => request<void>(`/datasets/${id}`, { method: "DELETE" }),

  // ─── Run Results ─────────────────────────────────────────────
  getRunResults: (runId: UUID, params?: { page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<PaginatedResponse<unknown>>(`/runs/${runId}/results${query}`);
  },
  getMetricResultsForItem: (runId: UUID, itemIndex: number) =>
    request<unknown[]>(`/runs/${runId}/items/${itemIndex}/metrics`),

  // ─── Analytics (extra endpoints) ─────────────────────────────
  getExperimentComparison: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/experiment-comparison${query}`);
  },
  getMetricDistribution: (runId: UUID) =>
    request<unknown>(`/analytics/metric-distribution/${runId}`),
  getPassFailSummary: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<unknown>(`/analytics/pass-fail-summary${query}`);
  },
  exportReport: (format: string, params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams({ format, ...Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])
    ) });
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<Blob>(`/analytics/reports/export${query}`, { method: "GET" });
  },

  // ─── Organizations ───────────────────────────────────────────
  listOrganizations: () => request<unknown[]>("/organizations"),
  createOrganization: (data: { name: string; slug: string; description?: string }) =>
    request<unknown>("/organizations", { method: "POST", body: JSON.stringify(data) }),
  getOrganization: (id: UUID) => request<unknown>(`/organizations/${id}`),
  updateOrganization: (id: UUID, data: Record<string, unknown>) =>
    request<unknown>(`/organizations/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteOrganization: (id: UUID) => request<void>(`/organizations/${id}`, { method: "DELETE" }),
  listMembers: (orgId: UUID) => request<unknown[]>(`/organizations/${orgId}/members`),
  inviteMember: (orgId: UUID, data: { email: string; role: string }) =>
    request<unknown>(`/organizations/${orgId}/members`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  changeMemberRole: (orgId: UUID, userId: UUID, data: { role: string }) =>
    request<unknown>(`/organizations/${orgId}/members/${userId}/role`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  removeMember: (orgId: UUID, userId: UUID) =>
    request<void>(`/organizations/${orgId}/members/${userId}`, { method: "DELETE" }),
  listInvitations: (orgId: UUID) => request<unknown[]>(`/organizations/${orgId}/invitations`),

  // ─── Projects ────────────────────────────────────────────────
  listProjects: (orgId: UUID) => request<unknown[]>(`/orgs/${orgId}/projects`),
  createProject: (orgId: UUID, data: { name: string; description?: string }) =>
    request<unknown>(`/orgs/${orgId}/projects`, { method: "POST", body: JSON.stringify(data) }),
  getProject: (orgId: UUID, projectId: UUID) =>
    request<unknown>(`/orgs/${orgId}/projects/${projectId}`),
  updateProject: (orgId: UUID, projectId: UUID, data: Record<string, unknown>) =>
    request<unknown>(`/orgs/${orgId}/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteProject: (orgId: UUID, projectId: UUID) =>
    request<void>(`/orgs/${orgId}/projects/${projectId}`, { method: "DELETE" }),

  // ─── API Keys ────────────────────────────────────────────────
  listApiKeys: () => request<unknown[]>("/api-keys"),
  createApiKey: (data: { name: string; scopes?: string[]; expires_in_days?: number }) =>
    request<unknown>("/api-keys", { method: "POST", body: JSON.stringify(data) }),
  revokeApiKey: (id: UUID) => request<unknown>(`/api-keys/${id}/revoke`, { method: "POST" }),
  rotateApiKey: (id: UUID) => request<unknown>(`/api-keys/${id}/rotate`, { method: "POST" }),
  deleteApiKey: (id: UUID) => request<void>(`/api-keys/${id}`, { method: "DELETE" }),

  // ─── Schedules ───────────────────────────────────────────────
  listSchedules: () => request<unknown[]>("/schedules"),
  createSchedule: (data: {
    name: string;
    schedule_type: string;
    cron_expression: string;
    task_config?: Record<string, unknown>;
    project_id?: string;
    timezone?: string;
  }) => request<unknown>("/schedules", { method: "POST", body: JSON.stringify(data) }),
  getSchedule: (id: UUID) => request<unknown>(`/schedules/${id}`),
  pauseSchedule: (id: UUID) => request<unknown>(`/schedules/${id}/pause`, { method: "POST" }),
  resumeSchedule: (id: UUID) => request<unknown>(`/schedules/${id}/resume`, { method: "POST" }),
  deleteSchedule: (id: UUID) => request<void>(`/schedules/${id}`, { method: "DELETE" }),

  // ─── Notifications ───────────────────────────────────────────
  listNotifications: (orgId: UUID, params?: { offset?: number; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.limit) qs.set("limit", String(params.limit));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ items: unknown[]; total: number }>(`/notifications/${orgId}${query}`);
  },
  sendNotification: (data: {
    channel: string;
    event: string;
    title: string;
    message: string;
    target?: string;
  }) => request<unknown>("/notifications/send", { method: "POST", body: JSON.stringify(data) }),

  // ─── Audit Logs ──────────────────────────────────────────────
  listAuditLogs: (
    orgId: UUID,
    params?: {
      action?: string;
      resource_type?: string;
      user_id?: string;
      offset?: number;
      limit?: number;
    },
  ) => {
    const qs = new URLSearchParams();
    if (params?.action) qs.set("action", params.action);
    if (params?.resource_type) qs.set("resource_type", params.resource_type);
    if (params?.user_id) qs.set("user_id", params.user_id);
    if (params?.offset) qs.set("offset", String(params.offset));
    if (params?.limit) qs.set("limit", String(params.limit));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<{ items: unknown[]; total: number }>(`/audit/${orgId}${query}`);
  },
};
