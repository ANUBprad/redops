"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

export default function NewAttackRunPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [definitionIds, setDefinitionIds] = useState<string>("");

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createAttackRun(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attack-runs"] });
      router.push("/redteam/runs");
    },
  });

  const handleSubmit = () => {
    const ids = definitionIds
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    createMutation.mutate({
      attack_definition_ids: ids,
      configuration: {},
    });
  };

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
              placeholder="e.g., uuid-1, uuid-2, uuid-3"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="target-model">Target Model</Label>
            <Input id="target-model" placeholder="gpt-4" defaultValue="gpt-4" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="target-provider">Target Provider</Label>
            <Select defaultValue="openai">
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="google">Google</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/redteam/runs">Cancel</Link>
        </Button>
        <Button onClick={handleSubmit} disabled={createMutation.isPending || !definitionIds}>
          {createMutation.isPending ? "Starting..." : "Start Attack Run"}
        </Button>
      </div>
    </div>
  );
}
