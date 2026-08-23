"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import type { TrendSeries } from "@/types/api";

export default function TrendsPage() {
  const [metricName, setMetricName] = useState("score");
  const [days, setDays] = useState(30);
  const [granularity, setGranularity] = useState("day");

  const { data, isLoading } = useQuery({
    queryKey: ["analytics", "trends", metricName, days, granularity],
    queryFn: () =>
      api.getHistoricalTrends({
        metric_name: metricName,
        days,
        granularity,
      }) as Promise<TrendSeries>,
  });

  const trend = data ?? {
    name: metricName,
    points: [],
    direction: "flat" as const,
    change_percent: 0,
  };

  const chartData = trend.points.map((p) => ({
    date: new Date(p.timestamp).toLocaleDateString(),
    value: p.value,
    label: p.label,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Trend Explorer</h1>
        <p className="text-muted-foreground">Analyze historical metric, cost, and latency trends</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="metric">Metric</Label>
          <Select value={metricName} onValueChange={setMetricName}>
            <option value="score">Score</option>
            <option value="cost">Cost</option>
            <option value="latency">Latency</option>
            <option value="safety">Safety</option>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="days">Time Range</Label>
          <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="granularity">Granularity</Label>
          <Select value={granularity} onValueChange={setGranularity}>
            <option value="day">Daily</option>
            <option value="week">Weekly</option>
            <option value="month">Monthly</option>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{trend.name} Trend</CardTitle>
          <div className="flex items-center gap-2">
            {trend.direction === "up" && (
              <Badge className="bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400">
                <TrendingUp className="mr-1 h-3 w-3" />+{trend.change_percent.toFixed(1)}%
              </Badge>
            )}
            {trend.direction === "down" && (
              <Badge className="bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400">
                <TrendingDown className="mr-1 h-3 w-3" />
                {trend.change_percent.toFixed(1)}%
              </Badge>
            )}
            {trend.direction === "flat" && (
              <Badge className="bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400">
                <Minus className="mr-1 h-3 w-3" />
                Stable
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-[300px] items-center justify-center text-muted-foreground">
              Loading trend data...
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex h-[300px] items-center justify-center text-muted-foreground">
              No data available for this time range
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {trend.points.length > 0 && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Latest Value</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {trend.points[trend.points.length - 1]?.value.toFixed(4) ?? "N/A"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Average</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(trend.points.reduce((s, p) => s + p.value, 0) / trend.points.length).toFixed(4)}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Data Points</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{trend.points.length}</div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
