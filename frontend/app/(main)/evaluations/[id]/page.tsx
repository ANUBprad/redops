"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface EvaluationDetail {
  id: string;
  project_id: string;
  dataset_id: string | null;
  name: string;
  description: string | null;
  provider: string;
  model: string;
  metrics: string[];
  tags: string[];
  configuration: Record<string, unknown>;
  status: string;
  created_by: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export default function EvaluationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = React.useState(false);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [provider, setProvider] = React.useState("");
  const [model, setModel] = React.useState("");

  const { data: evaluation, isLoading } = useQuery({
    queryKey: ["evaluation", id],
    queryFn: () => api.getEvaluation(id),
  });

  const updateMutation = useMutation({
    mutationFn: (updates: Record<string, unknown>) => api.updateEvaluation(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluation", id] });
      setIsEditing(false);
    },
  });

  if (isLoading) return <LoadingState />;
  if (!evaluation) return <div className="text-destructive">Evaluation not found</div>;

  const evalData = evaluation as EvaluationDetail;

  const handleSave = () => {
    updateMutation.mutate({ name, description, provider, model });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{evalData.name}</h1>
          <p className="text-muted-foreground">Evaluation definition</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => router.push(`/runs/new?eval=${id}`)}>
            Run Evaluation
          </Button>
          {isEditing ? (
            <>
              <Button variant="outline" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={updateMutation.isPending}>
                Save
              </Button>
            </>
          ) : (
            <Button
              onClick={() => {
                setIsEditing(true);
                setName(evalData.name);
                setDescription(evalData.description ?? "");
                setProvider(evalData.provider);
                setModel(evalData.model);
              }}
            >
              Edit
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {isEditing ? (
              <>
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Textarea value={description} onChange={(e) => setDescription(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Provider</Label>
                  <Input value={provider} onChange={(e) => setProvider(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Model</Label>
                  <Input value={model} onChange={(e) => setModel(e.target.value)} />
                </div>
              </>
            ) : (
              <>
                <div>
                  <span className="font-medium">Name:</span> {evalData.name}
                </div>
                <div>
                  <span className="font-medium">Description:</span> {evalData.description ?? "—"}
                </div>
                <div>
                  <span className="font-medium">Provider:</span> {evalData.provider}
                </div>
                <div>
                  <span className="font-medium">Model:</span> {evalData.model}
                </div>
                <div>
                  <span className="font-medium">Status:</span>{" "}
                  <Badge variant={evalData.status === "ready" ? "default" : "secondary"}>
                    {evalData.status}
                  </Badge>
                </div>
                <div>
                  <span className="font-medium">Metrics:</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {evalData.metrics.map((m) => (
                      <Badge key={m} variant="outline">
                        {m}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="font-medium">Tags:</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {evalData.tags.map((tag) => (
                      <Badge key={tag} variant="outline">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="font-medium">Version:</span> {evalData.version}
                </div>
                <div>
                  <span className="font-medium">Created:</span>{" "}
                  {new Date(evalData.created_at).toLocaleString()}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs">{JSON.stringify(evalData.configuration, null, 2)}</pre>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
