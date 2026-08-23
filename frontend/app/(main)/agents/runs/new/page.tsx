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

export default function NewAgentRunPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [agentName, setAgentName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4");
  const [tools, setTools] = useState("");
  const [maxSteps, setMaxSteps] = useState(10);
  const [timeoutSeconds, setTimeoutSeconds] = useState(300);
  const [tags, setTags] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createAgentRun(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
      router.push("/agents/runs");
    },
  });

  const handleSubmit = () => {
    const toolList = tools
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    const tagList = tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    createMutation.mutate({
      agent_name: agentName,
      provider,
      model,
      tools: toolList,
      max_steps: maxSteps,
      timeout_seconds: timeoutSeconds,
      tags: tagList,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">New Agent Run</h1>
        <p className="text-muted-foreground">Configure and start a new agent execution</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="agent-name">Agent Name *</Label>
            <Input
              id="agent-name"
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              placeholder="E.g., Research Assistant"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="provider">Provider *</Label>
              <Select value={provider} onValueChange={setProvider}>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="ollama">Ollama</option>
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
            <Label htmlFor="tools">Tools (comma-separated)</Label>
            <Input
              id="tools"
              value={tools}
              onChange={(e) => setTools(e.target.value)}
              placeholder="e.g., web_search, code_interpreter, file_manager"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="max-steps">Max Steps</Label>
              <Input
                id="max-steps"
                type="number"
                value={maxSteps}
                onChange={(e) => setMaxSteps(Number(e.target.value))}
                min={1}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timeout">Timeout (seconds)</Label>
              <Input
                id="timeout"
                type="number"
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
                min={1}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tags">Tags (comma-separated)</Label>
            <Input
              id="tags"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="e.g., production, safety-check"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/agents/runs">Cancel</Link>
        </Button>
        <Button onClick={handleSubmit} disabled={createMutation.isPending || !agentName}>
          {createMutation.isPending ? "Starting..." : "Start Agent Run"}
        </Button>
      </div>
    </div>
  );
}
