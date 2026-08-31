import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useParams: () => ({}),
  usePathname: () => "/redteam/runs/new",
}));

const toastError = vi.fn();
const toastSuccess = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
  },
}));

const createAttackRun = vi.fn();
const startAttackRun = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    createAttackRun: (...args: unknown[]) => createAttackRun(...args),
    startAttackRun: (...args: unknown[]) => startAttackRun(...args),
  },
}));

import NewAttackRunPage from "@/app/(main)/redteam/runs/new/page";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <NewAttackRunPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  pushMock.mockClear();
  toastError.mockClear();
  toastSuccess.mockClear();
  createAttackRun.mockReset();
  startAttackRun.mockReset();
});

describe("Red Team New Attack Run", () => {
  it("renders the run-start form", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "New Attack Run" })).toBeInTheDocument();
    expect(screen.getByLabelText("Target Provider")).toBeInTheDocument();
    expect(screen.getByLabelText("Target Model")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start Attack Run" })).toBeInTheDocument();
  });

  it("calls createAttackRun with attack definitions and target configuration", async () => {
    createAttackRun.mockResolvedValue({ id: "run-123" });

    renderPage();
    fireEvent.change(screen.getByLabelText("Attack Definition IDs (comma-separated)"), {
      target: { value: "def-1, def-2" },
    });
    fireEvent.change(screen.getByLabelText("Target Model"), { target: { value: "gpt-4o" } });
    fireEvent.click(screen.getByRole("button", { name: "Start Attack Run" }));

    await waitFor(() => {
      expect(createAttackRun).toHaveBeenCalledTimes(1);
    });

    const firstCall = createAttackRun.mock.calls[0] as [Record<string, unknown>] | undefined;
    expect(firstCall).toBeDefined();
    const payload = firstCall![0] as {
      attack_definition_ids: string[];
      configuration: { target_provider: string; target_model: string };
    };
    expect(payload.attack_definition_ids).toEqual(["def-1", "def-2"]);
    expect(payload.configuration.target_provider).toBe("openai");
    expect(payload.configuration.target_model).toBe("gpt-4o");
  });

  it("starts the run via startAttackRun after creation succeeds", async () => {
    createAttackRun.mockResolvedValue({ id: "run-abc" });
    startAttackRun.mockResolvedValue({ id: "run-abc", status: "running" });

    renderPage();
    fireEvent.change(screen.getByLabelText("Attack Definition IDs (comma-separated)"), {
      target: { value: "def-1, def-2, def-3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start Attack Run" }));

    await waitFor(() => {
      expect(startAttackRun).toHaveBeenCalledTimes(1);
    });

    const args = startAttackRun.mock.calls[0] as [string, { total_items: number }] | undefined;
    expect(args).toBeDefined();
    const [runId, data] = args!;
    expect(runId).toBe("run-abc");
    expect(data.total_items).toBe(3);
  });

  it("navigates to the runs list after the workflow is started", async () => {
    createAttackRun.mockResolvedValue({ id: "run-xyz" });
    startAttackRun.mockResolvedValue({ id: "run-xyz", status: "running" });

    renderPage();
    fireEvent.change(screen.getByLabelText("Attack Definition IDs (comma-separated)"), {
      target: { value: "def-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start Attack Run" }));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/redteam/runs");
    });
  });

  it("surfaces an error toast when the create request fails", async () => {
    createAttackRun.mockRejectedValue(new Error("Target provider is required"));

    renderPage();
    fireEvent.change(screen.getByLabelText("Attack Definition IDs (comma-separated)"), {
      target: { value: "def-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start Attack Run" }));

    await waitFor(() => {
      expect(toastError).toHaveBeenCalledWith("Target provider is required");
    });
  });

  it("does not start a run when creation succeeds without an id", async () => {
    createAttackRun.mockResolvedValue({});

    renderPage();
    fireEvent.change(screen.getByLabelText("Attack Definition IDs (comma-separated)"), {
      target: { value: "def-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start Attack Run" }));

    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/redteam/runs");
    });
    expect(startAttackRun).not.toHaveBeenCalled();
  });
});
