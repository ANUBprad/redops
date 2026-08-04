"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import { Clock } from "lucide-react";

interface TimelineEvent {
  event_id: string;
  run_id: string;
  event_type: string;
  data: Record<string, unknown>;
  correlation_id: string | null;
  occurred_at: string;
}

export function Timeline({ runId }: { runId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["timeline", runId],
    queryFn: () => api.getTimeline(runId, { limit: 100 }),
  });

  if (isLoading) return <LoadingState message="Loading timeline..." />;

  const events = (data?.items ?? []) as TimelineEvent[];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {events.map((event) => (
            <div key={event.event_id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className="h-2 w-2 rounded-full bg-primary" />
                <div className="h-full w-px bg-border" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {event.event_type}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    <Clock className="inline h-3 w-3 mr-1" />
                    {new Date(event.occurred_at).toLocaleTimeString()}
                  </span>
                </div>
                {event.data && Object.keys(event.data).length > 0 && (
                  <pre className="mt-1 text-xs text-muted-foreground">
                    {JSON.stringify(event.data)}
                  </pre>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
