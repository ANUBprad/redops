import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import { AlertCircle, CheckCircle, Info, Terminal } from "lucide-react";

interface LogEntry {
  log_id: string;
  run_id: string;
  level: string;
  source: string;
  message: string;
  metadata: Record<string, unknown>;
  correlation_id: string | null;
  timestamp: string;
}

const levelIcons: Record<string, React.ReactNode> = {
  DEBUG: <Info className="h-4 w-4 text-blue-500" />,
  INFO: <CheckCircle className="h-4 w-4 text-green-500" />,
  WARN: <AlertCircle className="h-4 w-4 text-yellow-500" />,
  ERROR: <Terminal className="h-4 w-4 text-red-500" />,
};

const levelColors: Record<string, string> = {
  DEBUG: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
  INFO: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400",
  WARN: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
  ERROR: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400",
};

export function LogViewer({ runId }: { runId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["logs", runId],
    queryFn: () => api.getLogs(runId, { limit: 200 }),
    refetchInterval: 5000,
  });

  if (isLoading) return <LoadingState message="Loading logs..." />;

  const logs = (data?.items ?? []) as LogEntry[];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Logs</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 max-h-96 overflow-y-auto font-mono text-xs">
          {logs.map((log) => (
            <div key={log.log_id} className="flex items-start gap-2 rounded-md border p-2">
              <div className="flex items-center gap-1">
                {levelIcons[log.level] ?? <Info className="h-4 w-4" />}
                <Badge className={levelColors[log.level] ?? "bg-muted"} variant="outline">
                  {log.level}
                </Badge>
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{log.source}</span>
                  <span className="text-muted-foreground">·</span>
                  <span className="text-muted-foreground">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="mt-1">{log.message}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
