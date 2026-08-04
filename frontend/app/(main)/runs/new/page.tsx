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

export default function NewEvaluationRunPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [evaluationName, setEvaluationName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4");
  const [totalItems, setTotalItems] = useState(100);

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createRun(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      router.push("/runs");
    },
  });

  const handleSubmit = () => {
    createMutation.mutate({
      evaluation_name: evaluationName,
      provider,
      model,
      total_items: totalItems,
      metrics: [],
      project_id: "proj-001",
      created_by: "user-1",
      tags: [],
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">New Evaluation Run</h1>
        <p className="text-muted-foreground">Configure and start a new evaluation run</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="evaluation-name">Evaluation Name *</Label>
            <Input
              id="evaluation-name"
              value={evaluationName}
              onChange={(e) => setEvaluationName(e.target.value)}
              placeholder="E.g., Production Safety Check"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="provider">Provider *</Label>
              <Select value={provider} onValueChange={setProvider}>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="model">Model *</Label>
              <Input
                id="model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="gpt-4"
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="total-items">Total Items</Label>
            <Input
              id="total-items"
              type="number"
              value={totalItems}
              onChange={(e) => setTotalItems(Number(e.target.value))}
              min={1}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/runs">Cancel</Link>
        </Button>
        <Button onClick={handleSubmit} disabled={createMutation.isPending || !evaluationName}>
          {createMutation.isPending ? "Starting..." : "Start Run"}
        </Button>
      </div>
    </div>
  );
}
