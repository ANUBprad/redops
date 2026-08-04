"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  LineChart,
  Line,
  CartesianGrid,
} from "recharts";

interface MetricResult {
  metric_name: string;
  score: number;
  normalized_score: number;
  raw_output: string;
  reasoning: string;
  execution_time_ms: number;
  error: string | null;
}

interface Aggregation {
  metric_name: string;
  mean: number;
  median: number;
  std_dev: number;
  min_score: number;
  max_score: number;
  item_count: number;
  success_count: number;
  error_count: number;
  success_rate: number;
}

export function MetricChart({ runId }: { runId: string }) {
  const { data: resultsData, isLoading: resultsLoading } = useQuery({
    queryKey: ["metric-results", runId],
    queryFn: () => api.getMetricResults(runId),
  });

  const { data: scoresData, isLoading: scoresLoading } = useQuery({
    queryKey: ["aggregated-scores", runId],
    queryFn: () => api.getAggregatedScores(runId),
  });

  if (resultsLoading || scoresLoading) return <LoadingState message="Loading metrics..." />;

  const results = (resultsData?.items ?? []) as MetricResult[];
  const aggregations = ((scoresData as { aggregations?: Aggregation[] })?.aggregations ?? []) as Aggregation[];

  const chartData = aggregations.map((a) => ({
    name: a.metric_name,
    mean: a.mean,
    median: a.median,
    min: a.min_score,
    max: a.max_score,
    successRate: a.success_rate * 100,
  }));

  const scoreDistribution = results.reduce(
    (acc, r) => {
      const bucket = Math.round(r.normalized_score * 10);
      acc[bucket] = (acc[bucket] ?? 0) + 1;
      return acc;
    },
    {} as Record<number, number>,
  );

  const distributionData = Array.from({ length: 11 }, (_, i) => ({
    score: `${i * 0.1}-${(i + 1) * 0.1}`,
    count: scoreDistribution[i] ?? 0,
  }));

  return (
    <div className="space-y-6">
      {chartData.length > 0 && (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 1]} />
              <Tooltip />
              <Legend />
              <Bar dataKey="mean" name="Mean" fill="#3b82f6" />
              <Bar dataKey="median" name="Median" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols(3)">
        {aggregations.map((agg) => (
          <Card key={agg.metric_name}>
            <CardContent className="pt-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">{agg.metric_name}</span>
                <Badge variant="outline">{agg.item_count} items</Badge>
              </div>
              <p className="text-2xl font-bold mt-2">{agg.mean.toFixed(3)}</p>
              <p className="text-xs text-muted-foreground">
                Median: {agg.median.toFixed(3)} · Std: {agg.std_dev.toFixed(3)}
              </p>
              <p className="text-xs text-muted-foreground">
                Success: {Math.round(agg.success_rate * 100)}% · Errors: {agg.error_count}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {distributionData.some((d) => d.count > 0) && (
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={distributionData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="score" />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#10b981" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
