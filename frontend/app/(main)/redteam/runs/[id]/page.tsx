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

interface AttackRunDetail {
  id: string;
  evaluation_run_id: string | null;
  status: string;
  attack_definition_ids: string[];
  configuration: Record<string, unknown>;
  items_total: number;
  items_completed: number;
  items_passed: number;
  items_violated: number;
  items_failed: number;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

const activeStatuses = new Set(["running", "queued", "created"]);

export default function AttackRunDetailPage() {
  const params = useParams<{ id: string }>();
  const runId = params?.id ?? "";
  const queryClient = useQueryClient();
  const [sseEvents, setSseEvents] = useState<string[]>([]);

  const {
    data: run,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["attack-run", runId],
    queryFn: () => api.getAttackRun(runId),
    enabled: !!runId,
    refetchInterval: 30000,
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelAttackRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attack-run", runId] });
      queryClient.invalidateQueries({ queryKey: ["attack-runs"] });
    },
  });

  useEffect(() => {
    if (!runId) return;
    const source = api.streamEvents(runId);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as { event_type: string };
        setSseEvents((prev) => [...prev.slice(-19), data.event_type]);
      } catch {
        // ignore
      }
    };

    source.onerror = () => source.close();
    return () => source.close();
  }, [runId]);

  const handleCancel = useCallback(() => {
    cancelMutation.mutate();
  }, [cancelMutation]);

  if (isLoading) return <LoadingState />;
  if (error || !run) return <div className="text-destructive">Error loading attack run</div>;

  const runData = run as AttackRunDetail;
  const canCancel = activeStatuses.has(runData.status);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Attack Run</h1>
          <p className="text-muted-foreground">
            Run ID: {runData.id} · {runData.attack_definition_ids.length} attack(s)
          </p>
        </div>
        <Badge
          className={
            runData.status === "completed"
              ? "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400"
              : runData.status === "running"
                ? "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400"
                : runData.status === "failed"
                  ? "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400"
                  : "bg-muted text-muted-foreground"
          }
        >
          {runData.status}
        </Badge>
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
              {runData.items_completed}/{runData.items_total} scenarios
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Passed</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{runData.items_passed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Violations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{runData.items_violated}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-600">{runData.items_failed}</div>
          </CardContent>
        </Card>
      </div>

      {sseEvents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Live Events ({sseEvents.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="max-h-48 space-y-1 overflow-y-auto">
              {sseEvents
                .slice()
                .reverse()
                .map((event, i) => (
                  <div key={i} className="text-xs">
                    <Badge variant="outline">{event}</Badge>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Attack Definitions</CardTitle>
        </CardHeader>
        <CardContent>
          {runData.attack_definition_ids.length === 0 ? (
            <p className="text-sm text-muted-foreground">No attack definitions linked</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {runData.attack_definition_ids.map((defId) => (
                <Link key={defId} href={`/redteam/definitions/${defId}`}>
                  <Badge variant="outline" className="cursor-pointer hover:bg-muted">
                    {defId.slice(0, 8)}...
                  </Badge>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">Run ID</dt>
              <dd className="font-mono">{runData.id}</dd>
            </div>
            {runData.evaluation_run_id && (
              <div>
                <dt className="text-muted-foreground">Evaluation Run</dt>
                <dd>
                  <Link
                    href={`/runs/${runData.evaluation_run_id}`}
                    className="font-mono text-blue-600 hover:underline"
                  >
                    {runData.evaluation_run_id.slice(0, 8)}...
                  </Link>
                </dd>
              </div>
            )}
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{new Date(runData.created_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Started</dt>
              <dd>
                {runData.started_at
                  ? new Date(runData.started_at).toLocaleString()
                  : "Not started"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Completed</dt>
              <dd>
                {runData.completed_at
                  ? new Date(runData.completed_at).toLocaleString()
                  : "Not completed"}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/redteam/runs">Back to Runs</Link>
        </Button>
        {canCancel && (
          <Button variant="destructive" onClick={handleCancel} disabled={cancelMutation.isPending}>
            {cancelMutation.isPending ? "Cancelling..." : "Cancel Run"}
          </Button>
        )}
      </div>
    </div>
  );
}
