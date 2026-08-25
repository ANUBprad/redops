"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Timeline } from "@/components/run/timeline";
import { LogViewer } from "@/components/run/log-viewer";
import { MetricChart } from "@/components/metrics/metric-chart";
import { LoadingState } from "@/components/ui/loading-state";
import { RotateCw, XCircle, Play, ArrowLeftRight } from "lucide-react";

interface RunDetail {
  id: string;
  evaluation_id: string | null;
  evaluation_name: string;
  workflow_id: string | null;
  provider: string;
  model: string;
  status: string;
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
  verdict: string | null;
  version: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const runId = params?.id ?? "";
  const queryClient = useQueryClient();
  const [sseEvents, setSseEvents] = useState<
    Array<{ event_type: string; data: Record<string, unknown> }>
  >([]);

  const {
    data: run,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    enabled: !!runId,
    refetchInterval: 30000,
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelRun(runId, { reason: "user_cancelled" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  const retryMutation = useMutation({
    mutationFn: () => api.retryRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  // SSE live updates
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

  if (isLoading) return <LoadingState />;
  if (error || !run) return <div className="text-destructive">Error loading run</div>;

  const runData = run as RunDetail;

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
      case "running":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400";
      case "failed":
        return "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400";
      case "queued":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400";
      case "cancelled":
        return "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  const getVerdictColor = (verdict: string) => {
    switch (verdict) {
      case "pass":
        return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
      case "fail":
        return "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400";
      case "error":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{runData.evaluation_name}</h1>
          <p className="text-muted-foreground">
            {runData.provider} · {runData.model} · Run ID: {runData.id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {runData.verdict && (
            <Badge className={getVerdictColor(runData.verdict)}>
              {runData.verdict.toUpperCase()}
            </Badge>
          )}
          <Badge className={getStatusColor(runData.status)}>{runData.status}</Badge>
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
              {runData.items_completed}/{runData.items_total} items
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
            <div className="text-2xl font-bold">${runData.cost.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground">
              Avg latency: {runData.average_latency_ms}ms
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{runData.items_failed}</div>
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

      <div className="grid gap-6 lg:grid-cols-2">
        <Timeline runId={runId} />
        <LogViewer runId={runId} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <MetricChart runId={runId} />
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        {runData.status === "completed" && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/runs/new?baseline=${runId}`)}
          >
            <ArrowLeftRight className="mr-2 h-4 w-4" />
            Compare
          </Button>
        )}
        {runData.status === "completed" && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => retryMutation.mutate()}
            disabled={retryMutation.isPending}
          >
            <RotateCw className="mr-2 h-4 w-4" />
            {retryMutation.isPending ? "Retrying..." : "Retry"}
          </Button>
        )}
        {runData.status === "running" && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => cancelMutation.mutate()}
            disabled={cancelMutation.isPending}
          >
            <XCircle className="mr-2 h-4 w-4" />
            {cancelMutation.isPending ? "Cancelling..." : "Cancel Run"}
          </Button>
        )}
      </div>
    </div>
  );
}
