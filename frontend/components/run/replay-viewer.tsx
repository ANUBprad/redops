"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import type { ReplayReport, ItemReport, MetricExplanation } from "@/types/api";

interface ReplayViewerProps {
  runId: string;
}

export function ReplayViewer({ runId }: ReplayViewerProps) {
  const [selectedItem, setSelectedItem] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["replay-report", runId],
    queryFn: () => api.getReplayReport(runId),
    enabled: !!runId,
  });

  if (isLoading) return <LoadingState />;
  if (error) return <div className="text-destructive">Error loading replay data</div>;
  if (!data) return <div className="text-muted-foreground">No replay data available</div>;

  const report = data as ReplayReport;
  const summary = report.summary;
  const items = report.item_reports;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.total_items}</div>
            <p className="text-xs text-muted-foreground">
              {summary.successful_items} succeeded · {summary.failed_items} failed
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Tokens</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(summary.total_tokens_input + summary.total_tokens_output).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              In: {summary.total_tokens_input.toLocaleString()} · Out:{" "}
              {summary.total_tokens_output.toLocaleString()}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Cost</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${summary.total_cost_usd.toFixed(4)}</div>
            <p className="text-xs text-muted-foreground">
              {summary.total_latency_ms.toLocaleString()}ms total
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {Object.entries(summary.metric_summaries).map(([name, ms]) => (
                <div key={name} className="flex justify-between text-xs">
                  <span className="text-muted-foreground truncate">{name}</span>
                  <span className="font-medium">{ms.mean.toFixed(3)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Item Execution Trace</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {items.map((item) => (
              <ItemRow
                key={item.item_index}
                item={item}
                isSelected={selectedItem === item.item_index}
                onSelect={() =>
                  setSelectedItem(selectedItem === item.item_index ? null : item.item_index)
                }
              />
            ))}
          </div>
        </CardContent>
      </Card>

      {selectedItem !== null && items[selectedItem] && (
        <ItemDetail item={items[selectedItem]} />
      )}
    </div>
  );
}

function ItemRow({
  item,
  isSelected,
  onSelect,
}: {
  item: ItemReport;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const hasError = !!item.error || !!item.provider_error;
  const avgScore =
    item.metric_explanations.length > 0
      ? item.metric_explanations.reduce((sum, m) => sum + m.normalized_score, 0) /
        item.metric_explanations.length
      : null;

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left rounded-lg border p-3 transition-colors ${
        isSelected
          ? "border-blue-500 bg-blue-50 dark:bg-blue-950/20"
          : "border-border hover:border-muted-foreground/50"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">#{item.item_index + 1}</span>
          <span className="text-sm text-muted-foreground truncate max-w-xs">
            {item.prompt_preview}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {hasError && <Badge variant="destructive">Error</Badge>}
          {avgScore !== null && (
            <Badge variant={avgScore >= 0.7 ? "default" : "secondary"}>
              {(avgScore * 100).toFixed(0)}%
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">
            {item.total_latency_ms.toLocaleString()}ms
          </span>
          <span className="text-xs text-muted-foreground">
            ${item.total_cost_usd.toFixed(4)}
          </span>
        </div>
      </div>
    </button>
  );
}

function ItemDetail({ item }: { item: ItemReport }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Item #{item.item_index + 1} Detail</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <h4 className="text-sm font-medium mb-1">Prompt</h4>
          <p className="text-sm text-muted-foreground whitespace-pre-wrap">{item.prompt_preview}</p>
        </div>

        <div>
          <h4 className="text-sm font-medium mb-1">Provider Response</h4>
          {item.provider_error ? (
            <p className="text-sm text-destructive">{item.provider_error}</p>
          ) : (
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {item.provider_response_preview}
            </p>
          )}
        </div>

        {item.error && (
          <div>
            <h4 className="text-sm font-medium mb-1">Item Error</h4>
            <p className="text-sm text-destructive">{item.error}</p>
          </div>
        )}

        <div>
          <h4 className="text-sm font-medium mb-2">Metric Scores</h4>
          <div className="space-y-2">
            {item.metric_explanations.map((me) => (
              <MetricRow key={me.metric_name} explanation={me} />
            ))}
          </div>
        </div>

        <div className="flex gap-4 text-xs text-muted-foreground">
          <span>Latency: {item.total_latency_ms.toLocaleString()}ms</span>
          <span>Cost: ${item.total_cost_usd.toFixed(4)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function MetricRow({ explanation }: { explanation: MetricExplanation }) {
  const scorePercent = Math.round(explanation.normalized_score * 100);
  const scoreColor =
    scorePercent >= 80
      ? "text-green-600"
      : scorePercent >= 50
        ? "text-yellow-600"
        : "text-red-600";

  return (
    <div className="rounded border p-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">{explanation.metric_name}</span>
        <span className={`text-sm font-bold ${scoreColor}`}>{scorePercent}%</span>
      </div>
      {explanation.reasoning && (
        <p className="text-xs text-muted-foreground">{explanation.reasoning}</p>
      )}
      <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
        <span>Confidence: {(explanation.confidence * 100).toFixed(0)}%</span>
        {explanation.judge_model && <span>Judge: {explanation.judge_model}</span>}
      </div>
    </div>
  );
}
