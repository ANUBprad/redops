"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { LoadingState } from "@/components/ui/loading-state";

interface AgentRunDetail {
  id: string;
  agent_definition_id: string | null;
  agent_name: string;
  workflow_id: string | null;
  provider: string;
  model: string;
  status: string;
  priority: string;
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

const statusColors: Record<string, string> = {
  completed: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400",
  queued: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
  timedout: "bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400",
  cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400",
  created: "bg-muted text-muted-foreground",
  starting: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
  paused: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
  cancelling: "bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400",
};

const retryableStatuses = new Set(["failed", "timedout", "cancelled"]);
const activeStatuses = new Set([
  "created",
  "queued",
  "starting",
  "running",
  "paused",
  "cancelling",
]);

export default function AgentRunDetailPage() {
  const params = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const runId = params?.id ?? "";
  const [sseEvents, setSseEvents] = useState<
    Array<{ event_type: string; data: Record<string, unknown> }>
  >([]);

  const {
    data: run,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["agent-run", runId],
    queryFn: () => api.getAgentRun(runId),
    enabled: !!runId,
    refetchInterval: 30000,
  });

  useEffect(() => {
    if (!runId) return;
    const source = api.streamEvents(runId);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          event_type?: string;
          data?: Record<string, unknown>;
        };
        setSseEvents((prev) => [
          ...prev.slice(-99),
          { event_type: data.event_type ?? "message", data: data.data ?? {} },
        ]);
      } catch {
        // ignore parse errors
      }
    };

    source.onerror = () => {
      source.close();
    };

    return () => source.close();
  }, [runId]);

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelAgentRun(runId, { reason: "user_cancelled" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-run", runId] });
      queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => api.retryAgentRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-run", runId] });
      queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
    },
  });

  const handleCancel = useCallback(() => {
    cancelMutation.mutate();
  }, [cancelMutation]);

  const handleRetry = useCallback(() => {
    retryMutation.mutate();
  }, [retryMutation]);

  if (isLoading) return <LoadingState />;
  if (error || !run) return <div className="text-destructive">Error loading agent run</div>;

  const runData = run as AgentRunDetail;
  const canCancel = activeStatuses.has(runData.status);
  const canRetry = retryableStatuses.has(runData.status);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{runData.agent_name}</h1>
          <p className="text-muted-foreground">
            {runData.provider} · {runData.model} · Run ID: {runData.id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className={statusColors[runData.status] ?? "bg-muted text-muted-foreground"}>
            {runData.status}
          </Badge>
          <Badge variant="outline">{runData.priority}</Badge>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{Math.round(runData.progress * 100)}%</div>
            <Progress value={runData.progress * 100} className="mt-2 h-2" />
            <p className="mt-1 text-xs text-muted-foreground">
              {runData.steps_completed}/{runData.steps_total} steps
              {runData.steps_failed > 0 && (
                <span className="text-red-600"> ({runData.steps_failed} failed)</span>
              )}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Tokens</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{runData.total_tokens.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              In: {runData.token_input.toLocaleString()} · Out:{" "}
              {runData.token_output.toLocaleString()}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Cost</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${runData.cost.toFixed(4)}</div>
            <p className="text-xs text-muted-foreground">
              Avg latency: {runData.average_latency_ms}ms
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Failure</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{runData.steps_failed}</div>
            {runData.failure_reason && (
              <p className="text-xs text-muted-foreground">{runData.failure_reason}</p>
            )}
          </CardContent>
        </Card>
      </div>

      {sseEvents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Live Events ({sseEvents.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-48 space-y-2 overflow-y-auto">
              {sseEvents
                .slice()
                .reverse()
                .map((event, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <Badge variant="outline">{event.event_type}</Badge>
                    <span className="text-muted-foreground">{JSON.stringify(event.data)}</span>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Run Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">Run ID</dt>
              <dd className="font-mono">{runData.id}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Workflow ID</dt>
              <dd className="font-mono">{runData.workflow_id ?? "N/A"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Agent Definition</dt>
              <dd>{runData.agent_definition_id ?? "Ad-hoc"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Version</dt>
              <dd>{runData.version}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{new Date(runData.created_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Started</dt>
              <dd>{runData.started_at ? new Date(runData.started_at).toLocaleString() : "N/A"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Completed</dt>
              <dd>
                {runData.completed_at ? new Date(runData.completed_at).toLocaleString() : "N/A"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Cancelled</dt>
              <dd>
                {runData.cancelled_at ? new Date(runData.cancelled_at).toLocaleString() : "N/A"}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/agents/runs">Back to Runs</Link>
        </Button>
        {canCancel && (
          <Button variant="destructive" onClick={handleCancel} disabled={cancelMutation.isPending}>
            {cancelMutation.isPending ? "Cancelling..." : "Cancel Run"}
          </Button>
        )}
        {canRetry && (
          <Button onClick={handleRetry} disabled={retryMutation.isPending}>
            {retryMutation.isPending ? "Retrying..." : "Retry Run"}
          </Button>
        )}
      </div>
    </div>
  );
}
