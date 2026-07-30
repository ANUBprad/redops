import { useState, useMemo } from "react";
import { Play, Search, ExternalLink } from "lucide-react";
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

interface AttackRun {
  id: string;
  evaluation_run_id: string | null;
  status: string;
  attack_definition_ids: string[];
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

export default function RedTeamRunsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ["attack-runs", { search, status: statusFilter, page, pageSize }],
    queryFn: () =>
      api.listAttackRuns({
        status: statusFilter ?? undefined,
        page,
        page_size: pageSize,
        sort_by: "created_at",
        sort_order: "desc",
      }),
  });

  const runs = useMemo(() => {
    return (data?.items ?? []) as AttackRun[];
  }, [data?.items]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed": return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
      case "running": return "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400";
      case "failed": return "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400";
      case "queued": return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400";
      case "cancelled": return "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400";
      default: return "bg-muted text-muted-foreground";
    }
  };

  if (isLoading) return <LoadingState />;
  if (error) return <div className="text-destructive">Error loading attack runs</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Red Team Runs</h1>
          <p className="text-muted-foreground">Monitor attack execution runs</p>
        </div>
        <Button asChild>
          <Link href="/redteam/runs/new">
            <Play className="mr-2 h-4 w-4" />
            New Attack Run
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search runs..."
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
        </Select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Attack Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b">
                  <th className="pb-2 text-sm font-medium">Run ID</th>
                  <th className="pb-2 text-sm font-medium">Status</th>
                  <th className="pb-2 text-sm font-medium">Progress</th>
                  <th className="pb-2 text-sm font-medium">Results</th>
                  <th className="pb-2 text-sm font-medium">Created</th>
                  <th className="pb-2 text-sm font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-b">
                    <td className="py-3 font-mono text-sm">{run.id.slice(0, 12)}...</td>
                    <td className="py-3">
                      <Badge className={getStatusColor(run.status)}>{run.status}</Badge>
                    </td>
                    <td className="py-3">{Math.round(run.progress * 100)}%</td>
                    <td className="py-3 text-sm">
                      <span className="text-green-600">{run.items_passed} passed</span>
                      {" · "}
                      <span className="text-red-600">{run.items_violated} violated</span>
                      {" · "}
                      <span className="text-gray-600">{run.items_failed} failed</span>
                    </td>
                    <td className="py-3 text-sm text-muted-foreground">
                      {new Date(run.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 text-right">
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/redteam/runs/${run.id}`}>
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
