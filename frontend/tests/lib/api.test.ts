import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "@/lib/api";

describe("api client", () => {
  it("creates an api object with expected methods", () => {
    expect(api.health).toBeDefined();
    expect(api.listEvaluations).toBeDefined();
    expect(api.createEvaluation).toBeDefined();
    expect(api.getRun).toBeDefined();
    expect(api.listMetrics).toBeDefined();
    expect(api.listAttackDefinitions).toBeDefined();
    expect(api.listAttackRuns).toBeDefined();
    expect(api.streamEvents).toBeDefined();
    expect(api.streamProgress).toBeDefined();
  });

  it("streamEvents returns EventSource", () => {
    const source = api.streamEvents("test-run-id");
    expect(source).toBeDefined();
    expect(source.readyState).toBeDefined();
    source.close();
  });

  it("streamProgress returns EventSource", () => {
    const source = api.streamProgress("test-run-id");
    expect(source).toBeDefined();
    expect(source.readyState).toBeDefined();
    source.close();
  });
});

describe("API request Authorization header", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "ok" }),
      headers: new Headers({ "content-type": "application/json" }),
    });
    global.fetch = fetchSpy;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    localStorage.removeItem("redops-access-token");
  });

  it("sends Authorization Bearer header when token exists", async () => {
    localStorage.setItem("redops-access-token", "test-jwt-token");

    await api.health();

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Headers).get("Authorization")).toBe("Bearer test-jwt-token");
  });

  it("does not send Authorization header when token is missing", async () => {
    localStorage.removeItem("redops-access-token");

    await api.health();

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Headers).get("Authorization")).toBeNull();
  });

  it("does not fabricate Authorization header for empty token", async () => {
    localStorage.removeItem("redops-access-token");

    await api.health();

    const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    const authHeader = (options.headers as Headers).get("Authorization");
    expect(authHeader).toBeNull();
  });
});

describe("SSE URL correctness", () => {
  it("streamEvents uses /api/v1 prefix in URL", () => {
    const source = api.streamEvents("run-123");
    const url = (source as any).url as string;
    expect(url).toContain("/api/v1/runs/run-123/events/stream");
    source.close();
  });

  it("streamProgress uses /api/v1 prefix in URL", () => {
    const source = api.streamProgress("run-456");
    const url = (source as any).url as string;
    expect(url).toContain("/api/v1/runs/run-456/progress/stream");
    source.close();
  });

  it("streamEvents URL contains /api/v1 prefix before run path", () => {
    const source = api.streamEvents("run-789");
    const url = (source as any).url as string;
    expect(url).toMatch(/\/api\/v1\/runs\/run-789\/events\/stream$/);
    source.close();
  });
});

describe("SSE authentication", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: () => Promise.resolve({ done: true, value: undefined }),
        }),
      },
      headers: new Headers(),
    });
    global.fetch = fetchSpy;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    localStorage.removeItem("redops-access-token");
  });

  it("SSE connection includes Authorization header when token exists", async () => {
    localStorage.setItem("redops-access-token", "sse-test-token");

    const source = api.streamEvents("run-auth");
    await new Promise((r) => setTimeout(r, 10));

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/runs/run-auth/events/stream");
    expect((options.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer sse-test-token",
    );
    source.close();
  });

  it("SSE connection does not send Authorization when token missing", async () => {
    localStorage.removeItem("redops-access-token");

    const source = api.streamEvents("run-noauth");
    await new Promise((r) => setTimeout(r, 10));

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect((options.headers as Record<string, string>)["Authorization"]).toBeUndefined();
    source.close();
  });
});
