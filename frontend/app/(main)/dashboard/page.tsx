"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Clock, FileText, PlayCircle, Shield, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { LoadingState } from "@/components/ui/loading-state";
import { api } from "@/lib/api";

const getStatusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
    case "running":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400";
    case "failed":
      return "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400";
    default:
      return "bg-muted text-muted-foreground";
  }
};

export default function DashboardPage() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: () => api.getDashboardSummary({ days: 30 }),
  });

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ["dashboard-runs"],
    queryFn: () =>
      api.listRuns({ page: 1, page_size: 5, sort_by: "created_at", sort_order: "desc" }),
  });

  const { data: safetyData } = useQuery({
    queryKey: ["dashboard-safety"],
    queryFn: () => api.getSafetyTrend({ days: 30 }),
  });

  if (summaryLoading || runsLoading) {
    return <LoadingState />;
  }

  const s = (summary as Record<string, unknown>) || {};
  const totalEvaluations = (s.total_evaluations as number) ?? 0;
  const completedRuns = (s.completed_runs as number) ?? 0;
  const totalRuns = (s.total_runs as number) ?? 0;
  const successRate = (s.success_rate as number) ?? 0;
  const avgCost = (s.average_cost as number) ?? 0;
  const safetyScore = (s.safety_score as number) ?? 0;

  const statCards = [
    {
      title: "Total Evaluations",
      value: String(totalEvaluations),
      icon: FileText,
      color: "text-blue-500",
    },
    {
      title: "Completed Runs",
      value: String(completedRuns),
      icon: PlayCircle,
      color: "text-green-500",
    },
    {
      title: "Total Runs",
      value: String(totalRuns),
      icon: Clock,
      color: "text-purple-500",
    },
    {
      title: "Success Rate",
      value: `${(successRate * 100).toFixed(1)}%`,
      icon: BarChart3,
      color: "text-amber-500",
    },
    {
      title: "Safety Score",
      value: `${(safetyScore * 100).toFixed(0)}%`,
      icon: Shield,
      color: safetyScore >= 0.9 ? "text-green-500" : "text-red-500",
    },
    {
      title: "Avg Cost",
      value: `$${avgCost.toFixed(4)}`,
      icon: TrendingUp,
      color: "text-teal-500",
    },
  ];

  const runs =
    ((runsData as unknown as Record<string, unknown>)?.items as Array<Record<string, unknown>>) ??
    [];

  const safety = (safetyData as Record<string, unknown>) || {};
  const safetyVerdicts = (safety.safety_verdicts as Record<string, number>) || {};
  const safeCount = safetyVerdicts.safe ?? 0;
  const violatedCount = safetyVerdicts.violated ?? 0;
  const totalSafety = safeCount + violatedCount;
  const safePercent = totalSafety > 0 ? Math.round((safeCount / totalSafety) * 100) : 0;
  const violatedPercent = totalSafety > 0 ? Math.round((violatedCount / totalSafety) * 100) : 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Overview of your evaluation platform</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {statCards.map((card) => (
          <Card key={card.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
              <card.icon className={`h-4 w-4 ${card.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Runs</CardTitle>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No runs yet. Create an evaluation and start a run.
              </p>
            ) : (
              <div className="space-y-4">
                {runs.map((run) => (
                  <div key={String(run.id)} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {String(run.evaluation_name || "Unnamed")}
                      </span>
                      <Badge className={getStatusColor(String(run.status))}>
                        {String(run.status)}
                      </Badge>
                    </div>
                    <Progress
                      value={
                        run.items_total
                          ? Math.round(
                              ((run.items_completed as number) / (run.items_total as number)) * 100,
                            )
                          : 0
                      }
                      className="h-2"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>
                        {String(run.items_completed ?? 0)}/{String(run.items_total ?? 0)} items
                      </span>
                      <span>Cost: ${((run.cost as number) ?? 0).toFixed(4)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Safety Overview</CardTitle>
          </CardHeader>
          <CardContent>
            {totalSafety === 0 ? (
              <p className="text-sm text-muted-foreground">
                No safety data available yet. Run a red-team campaign.
              </p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm">Safe</span>
                  <span className="text-sm font-medium text-green-600">{safePercent}% Safe</span>
                </div>
                <Progress value={safePercent} className="h-2" />
                <div className="flex items-center justify-between">
                  <span className="text-sm">Violated</span>
                  <span className="text-sm font-medium text-red-600">
                    {violatedPercent}% Violated
                  </span>
                </div>
                <Progress value={violatedPercent} className="h-2" />
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
