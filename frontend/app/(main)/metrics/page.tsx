"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  CartesianGrid,
} from "recharts";

interface MetricDefinition {
  name: string;
  display_name: string;
  description: string;
  category: string;
  scale: string;
  version: string;
  requires_context: boolean;
  default_weight: number;
  tags: string[];
}

export default function MetricsPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ["metrics"],
    queryFn: () => api.listMetrics(),
  });

  if (isLoading) return <LoadingState message="Loading metrics..." />;

  const metricList = (metrics ?? []) as MetricDefinition[];

  const categoryData = metricList.reduce(
    (acc, m) => {
      const cat = m.category;
      acc[cat] = (acc[cat] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  const chartData = Object.entries(categoryData).map(([category, count]) => ({
    category,
    count,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Metrics</h1>
        <p className="text-muted-foreground">Available evaluation metrics</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {metricList.map((metric) => (
          <Card key={metric.name}>
            <CardHeader>
              <CardTitle className="text-lg">{metric.display_name}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{metric.description}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge variant="outline">{metric.category}</Badge>
                <Badge variant="outline">{metric.scale}</Badge>
                {metric.requires_context && <Badge variant="secondary">Context</Badge>}
              </div>
              {metric.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {metric.tags.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {chartData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Metrics by Category</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" fill="#3b82f6" name="Count" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
