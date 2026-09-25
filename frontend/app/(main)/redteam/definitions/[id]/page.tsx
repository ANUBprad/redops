"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import Link from "next/link";
import { Trash2 } from "lucide-react";

interface AttackDefinitionDetail {
  id: string;
  name: string;
  description: string;
  category: string;
  severity: string;
  status: string;
  prompt_template: string;
  system_prompt_override: string | null;
  expected_behavior: string;
  parameters: Record<string, unknown>;
  tags: string[];
  created_by: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export default function AttackDefinitionDetailPage() {
  const params = useParams<{ id: string }>();
  const defId = params?.id ?? "";
  const router = useRouter();
  const queryClient = useQueryClient();

  const {
    data: definition,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["attack-definition", defId],
    queryFn: () => api.getAttackDefinition(defId),
    enabled: !!defId,
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteAttackDefinition(defId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attack-definitions"] });
      router.push("/redteam/definitions");
    },
  });

  if (isLoading) return <LoadingState />;
  if (error || !definition)
    return <div className="text-destructive">Error loading attack definition</div>;

  const def_ = definition as AttackDefinitionDetail;

  const severityColors: Record<string, string> = {
    low: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
    medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
    high: "bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400",
    critical: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{def_.name}</h1>
          <p className="text-muted-foreground">{def_.description}</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href={`/redteam/definitions/${def_.id}/edit`}>Edit</Link>
          </Button>
          <Button asChild>
            <Link href="/redteam/runs/new">Run Attack</Link>
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => {
              if (window.confirm("Delete this attack definition? This cannot be undone.")) {
                deleteMutation.mutate();
              }
            }}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Category</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline" className="text-sm">
              {def_.category}
            </Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Severity</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge className={severityColors[def_.severity] ?? "bg-muted"}>{def_.severity}</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant={def_.status === "active" ? "default" : "secondary"}>
              {def_.status}
            </Badge>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Prompt Template</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap rounded-md bg-muted p-4 text-sm">
              {def_.prompt_template}
            </pre>
          </CardContent>
        </Card>

        {def_.system_prompt_override && (
          <Card>
            <CardHeader>
              <CardTitle>System Prompt Override</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap rounded-md bg-muted p-4 text-sm">
                {def_.system_prompt_override}
              </pre>
            </CardContent>
          </Card>
        )}
      </div>

      {def_.expected_behavior && (
        <Card>
          <CardHeader>
            <CardTitle>Expected Behavior (Safe Response)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{def_.expected_behavior}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Tags</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {def_.tags.map((tag) => (
              <Badge key={tag} variant="outline">
                {tag}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium">Created by:</span> {def_.created_by ?? "—"}
            </div>
            <div>
              <span className="font-medium">Version:</span> {def_.version}
            </div>
            <div>
              <span className="font-medium">Created:</span>{" "}
              {new Date(def_.created_at).toLocaleString()}
            </div>
            <div>
              <span className="font-medium">Updated:</span>{" "}
              {new Date(def_.updated_at).toLocaleString()}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
