"use client";

import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/loading-state";
import { api } from "@/lib/api";
import type { DashboardSummary, SafetyTrend, GeneratedReport } from "@/types/api";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const SAFETY_COLORS = ["#22c55e", "#eab308", "#ef4444", "#dc2626"];

export default function ReportsPage() {
  const { data: dashboard, isLoading: dashboardLoading } = useQuery({
    queryKey: ["analytics-dashboard"],
    queryFn: () => api.getDashboardSummary(),
  });

  const { data: safety, isLoading: safetyLoading } = useQuery({
    queryKey: ["analytics-safety"],
    queryFn: () => api.getSafetyTrend(),
  });

  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ["analytics-trends"],
    queryFn: () => api.getHistoricalTrends(),
  });

  const { data: report } = useQuery({
    queryKey: ["analytics-report"],
    queryFn: () => api.generateReport(),
  });

  if (dashboardLoading || safetyLoading) return <LoadingState />;

  const summary = dashboard as DashboardSummary | undefined;
  const safetyData = safety as SafetyTrend | undefined;
  const trendData = trends as { series?: { name: string; points: { timestamp: string; value: number }[] }[] } | undefined;
  const reportData = report as GeneratedReport | undefined;

  const safetyPieData = safetyData?.safety_by_dimension?.map((d) => ({
    name: d.dimension,
    value: d.sample_count,
    color: SAFETY_COLORS[
      d.verdict === "safe" ? 0 : d.verdict === "suspicious" ? 1 : d.verdict === "violated" ? 2 : 3
    ] ?? "#6b7280",
  })) ?? [];

  const trendBarData = trendData?.series?.[0]?.points?.map((p) => ({
    name: new Date(p.timestamp).toLocaleDateString("en-US", { month: "short" }),
    value: p.value,
  })) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="text-muted-foreground">Evaluation and safety reports</p>
        </div>
        <Button variant="outline">
          <Download className="mr-2 h-4 w-4" />
          Export
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Evaluations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.total_evaluations ?? "—"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Completed Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.completed_runs ?? "—"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Safety Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary?.average_safety_score != null
                ? `${(summary.average_safety_score * 100).toFixed(1)}%`
                : "—"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Cost / Run</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summary?.average_cost != null ? `$${summary.average_cost.toFixed(4)}` : "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Historical Trends</CardTitle>
          </CardHeader>
          <CardContent>
            {trendsLoading ? (
              <LoadingState message="Loading trends..." />
            ) : trendBarData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trendBarData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" name="Score" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">No trend data available</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Safety Verdict Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {safetyPieData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={safetyPieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ name, percent }) =>
                        `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`
                      }
                    >
                      {safetyPieData.map((entry, i) => (
                        <Cell key={`cell-${i}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No safety data available
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {reportData && (
        <Card>
          <CardHeader>
            <CardTitle>{reportData.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">{reportData.description}</p>
            {reportData.recommendations.length > 0 && (
              <div>
                <h3 className="font-medium mb-2">Recommendations</h3>
                <ul className="space-y-1">
                  {reportData.recommendations.map((rec, i) => (
                    <li key={i} className="text-sm text-muted-foreground">• {rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
