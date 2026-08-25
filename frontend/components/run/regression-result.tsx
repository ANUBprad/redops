"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import type { RegressionResult, MetricRegression } from "@/types/api";

interface RegressionResultProps {
  baselineRunId: string;
  currentRunId: string;
}

export function RegressionResultView({ baselineRunId, currentRunId }: RegressionResultProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["regression", baselineRunId, currentRunId],
    queryFn: () => api.analyzeRegression(baselineRunId, currentRunId),
    enabled: !!baselineRunId && !!currentRunId,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <div className="text-destructive">Error loading regression analysis</div>;
  if (!data) return null;

  const result = data as RegressionResult;

  const verdictColor =
    {
      pass: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400",
      fail: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400",
      not_comparable: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
      error: "bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400",
    }[result.verdict] ?? "bg-muted text-muted-foreground";

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Verdict</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge className={verdictColor}>{result.verdict.toUpperCase()}</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Regressions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{result.regression_count}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">{result.error_count}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Fingerprints</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm">
              {result.fingerprints_compatible ? (
                <Badge className="bg-green-100 text-green-800">Compatible</Badge>
              ) : (
                <Badge className="bg-yellow-100 text-yellow-800">Different</Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {result.reasoning && (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{result.reasoning}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Metric Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {result.metric_comparisons.map((mc) => (
              <MetricRegressionRow key={mc.metric_name} comparison={mc} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricRegressionRow({ comparison }: { comparison: MetricRegression }) {
  const statusColor =
    {
      pass: "bg-green-100 text-green-800",
      regression: "bg-red-100 text-red-800",
      improvement: "bg-blue-100 text-blue-800",
      no_change: "bg-gray-100 text-gray-800",
      not_comparable: "bg-yellow-100 text-yellow-800",
      added: "bg-purple-100 text-purple-800",
      removed: "bg-orange-100 text-orange-800",
      error: "bg-red-100 text-red-800",
    }[comparison.status] ?? "bg-muted text-muted-foreground";

  return (
    <div className="flex items-center justify-between rounded border p-2">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{comparison.metric_name}</span>
          <Badge className={statusColor}>{comparison.status}</Badge>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{comparison.reasoning}</p>
      </div>
      <div className="text-right text-sm">
        {comparison.baseline_score !== null && comparison.current_score !== null ? (
          <span>
            {comparison.baseline_score.toFixed(3)} → {comparison.current_score.toFixed(3)}
            <span className={`ml-2 ${comparison.delta >= 0 ? "text-green-600" : "text-red-600"}`}>
              ({comparison.delta >= 0 ? "+" : ""}
              {(comparison.delta * 100).toFixed(1)}%)
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground">N/A</span>
        )}
      </div>
    </div>
  );
}
