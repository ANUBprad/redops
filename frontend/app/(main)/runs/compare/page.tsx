"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/ui/loading-state";
import { RegressionResultView } from "@/components/run/regression-result";
import type { TraceComparison } from "@/types/api";

export default function ComparePage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <CompareContent />
    </Suspense>
  );
}

function CompareContent() {
  const searchParams = useSearchParams();
  const [baselineId, setBaselineId] = useState(searchParams.get("baseline") ?? "");
  const [comparisonId, setComparisonId] = useState(searchParams.get("comparison") ?? "");

  const { data, isLoading, error } = useQuery<TraceComparison | undefined>({
    queryKey: ["compare", baselineId, comparisonId],
    queryFn: () => api.compareRuns(baselineId, comparisonId) as Promise<TraceComparison>,
    enabled: !!baselineId && !!comparisonId,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Compare Runs</h1>
        <p className="text-muted-foreground">Compare metric results between two evaluation runs</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Select Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">Baseline Run ID</label>
              <Input
                placeholder="Enter baseline run ID"
                value={baselineId}
                onChange={(e) => setBaselineId(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">Comparison Run ID</label>
              <Input
                placeholder="Enter comparison run ID"
                value={comparisonId}
                onChange={(e) => setComparisonId(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {isLoading && <LoadingState />}
      {error && <div className="text-destructive">Error loading comparison data</div>}

      {data && <ComparisonResult result={data} />}

      {baselineId && comparisonId && (
        <div className="space-y-4">
          <h2 className="text-2xl font-bold">Regression Analysis</h2>
          <RegressionResultView baselineRunId={baselineId} currentRunId={comparisonId} />
        </div>
      )}
    </div>
  );
}

function ComparisonResult({ result }: { result: TraceComparison }) {
  const winnerColor =
    result.winner === "baseline"
      ? "text-blue-600"
      : result.winner === "comparison"
        ? "text-green-600"
        : "text-muted-foreground";

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Baseline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">{result.baseline_provider}</div>
            <div className="text-sm text-muted-foreground">{result.baseline_model}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              Run: {result.baseline_run_id.slice(0, 8)}...
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">{result.comparison_provider}</div>
            <div className="text-sm text-muted-foreground">{result.comparison_model}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              Run: {result.comparison_run_id.slice(0, 8)}...
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Result</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-lg font-bold ${winnerColor}`}>
              {result.winner === "tie" ? "Tie" : `${result.winner} wins`}
            </div>
            <div className="text-sm text-muted-foreground">
              Confidence: {(result.confidence * 100).toFixed(0)}%
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              Cost delta: ${result.cost_delta.toFixed(4)}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Metric Deltas</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {Object.entries(result.metric_deltas).map(([metric, delta]) => (
              <div key={metric} className="flex items-center justify-between rounded border p-2">
                <span className="text-sm font-medium">{metric}</span>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-muted-foreground">{delta.baseline_mean.toFixed(3)}</span>
                  <span>→</span>
                  <span className="font-medium">{delta.comparison_mean.toFixed(3)}</span>
                  <Badge
                    variant={delta.delta >= 0 ? "default" : "secondary"}
                    className={
                      delta.delta >= 0 ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                    }
                  >
                    {delta.delta >= 0 ? "+" : ""}
                    {(delta.delta * 100).toFixed(1)}%
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
