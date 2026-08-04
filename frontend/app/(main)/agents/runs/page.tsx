"use client";

import { useState, useMemo } from "react";
import { Play, Search, Filter, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { LoadingState } from "@/components/ui/loading-state";
import { Pagination } from "@/components/ui/pagination";

interface AgentRunSummary {
  id: string;
  agent_definition_id: string | null;
  agent_name: string;
  provider: string;
  model: string;
  status: string;
  progress: number;
  steps_total: number;
  steps_completed: number;
  steps_failed: number;
  cost: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
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

export default function AgentRunsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ["agent-runs", { search, status: statusFilter, page, pageSize }],
    queryFn: () =>
      api.listAgentRuns({
        search: search || undefined,
        status: statusFilter ?? undefined,
        page,
        page_size: pageSize,
        sort_by: "created_at",
        sort_order: "desc",
      }),
    refetchInterval: 30000,
  });

  const runs = useMemo(() => {
    return (data?.items ?? []) as AgentRunSummary[];
  }, [data?.items]);

  if (isLoading) return <LoadingState />;
  if (error) return <div className="text-destructive">Error loading agent runs</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Agent Runs</h1>
          <p className="text-muted-foreground">Monitor agent execution runs</p>
        </div>
        <Button asChild>
          <Link href="/agents/runs/new">
            <Play className="mr-2 h-4 w-4" />
            New Agent Run
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search agent runs..."
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={statusFilter ?? "all"} onValueChange={(v) => setStatusFilter(v === "all" ? null : v)}>
          <option value="all">All Status</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="queued">Queued</option>
          <option value="cancelled">Cancelled</option>
          <option value="timedout">Timed Out</option>
        </Select>
        <Button variant="outline" size="sm">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th className="pb-2 text-sm font-medium">Agent</th>
                  <th className="pb-2 text-sm font-medium">Status</th>
                  <th className="pb-2 text-sm font-medium">Progress</th>
                  <th className="pb-2 text-sm font-medium">Steps</th>
                  <th className="pb-2 text-sm font-medium">Cost</th>
                  <th className="pb-2 text-sm font-medium">Created</th>
                  <th className="pb-2 text-sm font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-b">
                    <td className="py-3">
                      <Link
                        href={`/agents/runs/${run.id}`}
                        className="font-medium hover:underline"
                      >
                        {run.agent_name}
                      </Link>
                      <div className="text-sm text-muted-foreground">
                        {run.provider} · {run.model}
                      </div>
                    </td>
                    <td className="py-3">
                      <Badge className={statusColors[run.status] ?? "bg-muted text-muted-foreground"}>
                        {run.status}
                      </Badge>
                    </td>
                    <td className="py-3">
                      <div className="text-sm">{Math.round(run.progress * 100)}%</div>
                    </td>
                    <td className="py-3 text-sm">
                      {run.steps_completed}/{run.steps_total}
                      {run.steps_failed > 0 && (
                        <span className="text-red-600"> ({run.steps_failed} failed)</span>
                      )}
                    </td>
                    <td className="py-3 text-sm">${run.cost.toFixed(4)}</td>
                    <td className="py-3 text-sm text-muted-foreground">
                      {new Date(run.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/agents/runs/${run.id}`}>
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {data && data.total > 0 && (
        <Pagination
          current={data.page}
          total={data.total}
          pageSize={data.page_size}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
