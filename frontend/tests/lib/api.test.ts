import { describe, it, expect } from "vitest";
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
});
