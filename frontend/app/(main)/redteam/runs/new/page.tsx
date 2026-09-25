"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

function parseDefinitionIds(raw: string): string[] {
  return raw
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
}

function errorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return "Failed to create attack run";
}

export default function NewAttackRunPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [definitionIds, setDefinitionIds] = useState("");
  const [targetProvider, setTargetProvider] = useState("openai");
  const [targetModel, setTargetModel] = useState("gpt-4");

  const startMutation = useMutation({
    mutationFn: ({ runId, ids }: { runId: string; ids: string[] }) =>
      api.startAttackRun(runId, { total_items: ids.length }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attack-runs"] });
      toast.success("Attack run started");
      router.push("/redteam/runs");
    },
    onError: () => {
      toast.error("Attack run was created but could not be started");
      router.push("/redteam/runs");
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createAttackRun(data),
    onSuccess: (run) => {
      const runId = (run as { id?: string } | null)?.id;
      if (!runId) {
        queryClient.invalidateQueries({ queryKey: ["attack-runs"] });
        toast.error("Attack run was created without an id");
        router.push("/redteam/runs");
        return;
      }
      startMutation.mutate({ runId, ids: parseDefinitionIds(definitionIds) });
    },
    onError: (err) => {
      toast.error(errorMessage(err));
    },
  });

  const handleSubmit = () => {
    const ids = parseDefinitionIds(definitionIds);
    createMutation.mutate({
      attack_definition_ids: ids,
      configuration: {
        target_provider: targetProvider,
        target_model: targetModel,
      },
    });
  };

  const isSubmitting = createMutation.isPending || startMutation.isPending;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">New Attack Run</h1>
        <p className="text-muted-foreground">
          Select attack definitions to run against your target
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="definition-ids">Attack Definition IDs (comma-separated)</Label>
            <Input
              id="definition-ids"
              value={definitionIds}
              onChange={(e) => setDefinitionIds(e.target.value)}
              disabled={isSubmitting}
              placeholder="e.g., uuid-1, uuid-2, uuid-3"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="target-provider">Target Provider</Label>
              <Select
                id="target-provider"
                value={targetProvider}
                onValueChange={setTargetProvider}
                disabled={isSubmitting}
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="target-model">Target Model</Label>
              <Input
                id="target-model"
                value={targetModel}
                onChange={(e) => setTargetModel(e.target.value)}
                disabled={isSubmitting}
                placeholder="gpt-4"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/redteam/runs">Cancel</Link>
        </Button>
        <Button onClick={handleSubmit} disabled={isSubmitting || !definitionIds.trim()}>
          {isSubmitting ? "Starting..." : "Start Attack Run"}
        </Button>
      </div>
    </div>
  );
}
