"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Trophy, Medal } from "lucide-react";
import type { ComparisonResult } from "@/types/api";

export default function ComparisonsPage() {
  const [entityType, setEntityType] = useState("model");
  const [entityIds, setEntityIds] = useState("");
  const [days, setDays] = useState(30);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["analytics", "comparison", entityType, entityIds, days],
    queryFn: () =>
      api.getComparison({
        entity_type: entityType,
        entity_ids: entityIds,
        days,
      }) as Promise<ComparisonResult>,
    enabled: false,
  });

  const comparison = data ?? { title: "", compared_items: [], metrics: [], summary: "" };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Model Comparison</h1>
        <p className="text-muted-foreground">Compare models and providers across metrics</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Compare</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="space-y-2">
              <Label>Entity Type</Label>
              <Select value={entityType} onValueChange={setEntityType}>
                <option value="model">Model</option>
                <option value="provider">Provider</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Entity IDs (comma-separated)</Label>
              <Input
                placeholder="e.g., gpt-4,claude-3"
                value={entityIds}
                onChange={(e) => setEntityIds(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Time Range</Label>
              <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
                <option value="7">Last 7 days</option>
                <option value="14">Last 14 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>&nbsp;</Label>
              <Button className="w-full" onClick={() => refetch()} disabled={isLoading}>
                {isLoading ? "Comparing..." : "Compare"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {comparison.compared_items.length > 0 && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{comparison.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-sm text-muted-foreground">{comparison.summary}</p>

              {comparison.metrics.map((metric) => (
                <div key={metric.metric_name} className="mb-6">
                  <h3 className="mb-3 text-lg font-semibold">{metric.metric_name}</h3>
                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {metric.values.map((val) => (
                      <div
                        key={val.entity_id}
                        className={`rounded-lg border p-3 ${
                          val.entity_id === metric.best_entity_id
                            ? "border-green-500 bg-green-50 dark:bg-green-900/10"
                            : "border-border"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{val.entity_id}</span>
                          {val.entity_id === metric.best_entity_id && (
                            <Trophy className="h-4 w-4 text-yellow-500" />
                          )}
                        </div>
                        <div className="mt-1 text-xl font-bold">{val.formatted_value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}

      {comparison.compared_items.length === 0 && !isLoading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Medal className="mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">
              Enter entity IDs and click Compare to see results
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
