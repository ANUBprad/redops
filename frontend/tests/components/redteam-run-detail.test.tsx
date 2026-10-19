import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mocks = vi.hoisted(() => ({
  getAttackRun: vi.fn(),
  cancelAttackRun: vi.fn(),
  streamEvents: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "run-123" }),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getAttackRun: (...args: unknown[]) => mocks.getAttackRun(...args),
    cancelAttackRun: (...args: unknown[]) => mocks.cancelAttackRun(...args),
    streamEvents: (...args: unknown[]) => mocks.streamEvents(...args),
  },
}));

import AttackRunDetailPage from "@/app/(main)/redteam/runs/[id]/page";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AttackRunDetailPage />
    </QueryClientProvider>,
  );
}

describe("Red Team Attack Run Detail", () => {
  beforeEach(() => {
    mocks.getAttackRun.mockReset();
    mocks.cancelAttackRun.mockReset();
    mocks.streamEvents.mockReset();
    mocks.streamEvents.mockReturnValue({
      onmessage: null,
      onerror: null,
      close: vi.fn(),
    });
  });

  it("renders persisted per-round prompts, responses, judge evidence, and cost scope", async () => {
    mocks.getAttackRun.mockResolvedValue({
      id: "run-123",
      evaluation_run_id: null,
      status: "completed",
      attack_definition_ids: ["definition-123"],
      configuration: { target_provider: "openai", target_model: "gpt-4o" },
      items_total: 1,
      items_completed: 1,
      items_passed: 0,
      items_violated: 1,
      items_failed: 0,
      progress: 1,
      started_at: "2026-10-16T00:00:00Z",
      completed_at: "2026-10-16T00:01:00Z",
      created_at: "2026-10-16T00:00:00Z",
      campaign_results: {
        state: "completed",
        total_rounds: 1,
        total_attacks: 1,
        total_tokens: 15,
        total_cost_usd: 0.001,
        cost_scope: "target_calls_only",
        violation_count: 1,
        severe_violation_count: 0,
        rounds: [
          {
            round_number: 1,
            attack_category: "prompt_injection",
            tokens_used: 15,
            cost_usd: 0.001,
            execution: {
              attack_prompt: "Use the selected attack definition",
              target_response: "I will not follow that instruction.",
              cost_usd: 0.001,
              provider_name: "openai",
              model_name: "gpt-4o",
            },
            effectiveness: {
              is_violation: true,
              is_violation_severe: false,
              evaluation_source: "semantic_judge",
              semantic_verdict: "SUCCESS",
              semantic_reasoning: "The response fulfilled the objective.",
              semantic_evidence: "Here are the requested steps.",
              semantic_judge_cost_usd: 0.0002,
              reasoning: "Semantic judgment completed.",
            },
          },
        ],
      },
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Campaign Results")).toBeInTheDocument();
    });
    expect(screen.getByText("Use the selected attack definition")).toBeInTheDocument();
    expect(screen.getByText("I will not follow that instruction.")).toBeInTheDocument();
    expect(screen.getByText("The response fulfilled the objective.")).toBeInTheDocument();
    expect(screen.getByText(/Cost scope:.*target calls only/)).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, node) =>
          node?.tagName.toLowerCase() === "p" &&
          (node.textContent?.includes("Judge cost: $0.000200") ?? false),
      ),
    ).toBeInTheDocument();
  });
});
