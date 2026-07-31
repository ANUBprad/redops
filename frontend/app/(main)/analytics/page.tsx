"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Clock,
  DollarSign,
  Shield,
  Target,
  Activity,
} from "lucide-react";
import type { DashboardSummary } from "@/types/api";

function StatCard({
  title,
  value,
  icon: Icon,
  description,
  trend,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  description?: string;
  trend?: "up" | "down" | "flat";
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            {trend === "up" && <TrendingUp className="h-3 w-3 text-green-500" />}
            {trend === "down" && <TrendingDown className="h-3 w-3 text-red-500" />}
            {description}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function getStatusColor(status: string) {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
    case "running":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400";
    case "failed":
      return "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400";
    case "queued":
      return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400";
    default:
      return "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400";
  }
}

export default function AnalyticsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["analytics", "dashboard"],
    queryFn: () => api.getDashboardSummary({ days: 30 }) as Promise<DashboardSummary>,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-muted-foreground">Loading analytics...</div>
      </div>
    );
  }

  const summary = data ?? {
    total_evaluations: 0,
    completed_runs: 0,
    success_rate: 0,
    average_score: 0,
    average_latency_ms: 0,
    average_cost: 0,
    total_token_usage: 0,
    average_safety_score: 0,
    attack_success_rate: 0,
    recent_activity: [],
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Analytics Dashboard</h1>
        <p className="text-muted-foreground">
          Enterprise analytics and reporting overview
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Evaluations"
          value={summary.total_evaluations}
          icon={Target}
          description="All time"
        />
        <StatCard
          title="Completed Runs"
          value={summary.completed_runs}
          icon={Activity}
          description={`${summary.success_rate}% success rate`}
          trend={summary.success_rate >= 80 ? "up" : "down"}
        />
        <StatCard
          title="Average Cost"
          value={`$${summary.average_cost.toFixed(4)}`}
          icon={DollarSign}
          description="Per run"
        />
        <StatCard
          title="Average Latency"
          value={`${summary.average_latency_ms.toFixed(0)}ms`}
          icon={Clock}
          description="Per item"
        />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Token Usage"
          value={summary.total_token_usage.toLocaleString()}
          icon={BarChart3}
          description="Input + Output"
        />
        <StatCard
          title="Safety Score"
          value={`${summary.average_safety_score.toFixed(1)}%`}
          icon={Shield}
          description="Average across attacks"
          trend={summary.average_safety_score >= 90 ? "up" : "down"}
        />
        <StatCard
          title="Attack Success Rate"
          value={`${summary.attack_success_rate.toFixed(1)}%`}
          icon={Shield}
          description="Violations / Total attacks"
          trend={summary.attack_success_rate <= 10 ? "up" : "down"}
        />
        <StatCard
          title="Success Rate"
          value={`${summary.success_rate.toFixed(1)}%`}
          icon={TrendingUp}
          description="Completed / Total runs"
          trend={summary.success_rate >= 80 ? "up" : "down"}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {summary.recent_activity.length === 0 ? (
            <p className="text-muted-foreground text-sm">No recent activity</p>
          ) : (
            <div className="space-y-3">
              {summary.recent_activity.map((activity) => (
                <div
                  key={activity.id}
                  className="flex items-center justify-between border-b pb-3 last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium">{activity.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {activity.type === "evaluation_run" ? "Evaluation Run" : "Attack Run"}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">{activity.summary}</span>
                    <Badge className={getStatusColor(activity.status)}>
                      {activity.status}
                    </Badge>
                    {activity.timestamp && (
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {new Date(activity.timestamp).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
