"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";

export default function NewEvaluationPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4");
  const [metrics, _setMetrics] = useState<string[]>(["accuracy"]);
  const [tags, setTags] = useState<string>("");

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createEvaluation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluations"] });
      router.push("/evaluations");
    },
  });

  const handleSubmit = () => {
    createMutation.mutate({
      project_id: "proj-001",
      name,
      description,
      provider,
      model,
      metrics: metrics,
      tags: tags ? tags.split(",").map((t) => t.trim()) : [],
      configuration: {},
      created_by: "user-1",
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Create Evaluation</h1>
        <p className="text-muted-foreground">Define a new evaluation</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Evaluation Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Evaluation"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this evaluation measure?"
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
            <Label htmlFor="tags">Tags (comma separated)</Label>
            <Input
              id="tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="safety, accuracy, production"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => router.push("/evaluations")}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={createMutation.isPending || !name}>
          {createMutation.isPending ? "Creating..." : "Create Evaluation"}
        </Button>
      </div>
    </div>
  );
}
