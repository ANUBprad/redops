"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
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
import { Badge } from "@/components/ui/badge";

export default function NewAttackDefinitionPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("prompt_injection");
  const [severity, setSeverity] = useState("medium");
  const [promptTemplate, setPromptTemplate] = useState("");
  const [systemPromptOverride, setSystemPromptOverride] = useState("");
  const [expectedBehavior, setExpectedBehavior] = useState("");
  const [tags, setTags] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createAttackDefinition(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attack-definitions"] });
      router.push("/redteam/definitions");
    },
  });

  const handleSubmit = () => {
    createMutation.mutate({
      name,
      description,
      category,
      severity,
      prompt_template: promptTemplate,
      system_prompt_override: systemPromptOverride || undefined,
      expected_behavior: expectedBehavior,
      parameters: {},
      tags: tags ? tags.split(",").map((t) => t.trim()) : [],
      created_by: "user-1",
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">New Attack Definition</h1>
          <p className="text-muted-foreground">Create a new attack template for testing</p>
        </div>
        <Button asChild variant="outline">
          <Link href="/redteam/definitions">
            <Trash2 className="mr-2 h-4 w-4" />
            Cancel
          </Link>
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Attack Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Name *</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="E.g., Direct Prompt Injection"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What this attack tests..."
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="category">Category *</Label>
                  <Select value={category} onValueChange={setCategory}>
                    <option value="prompt_injection">Prompt Injection</option>
                    <option value="jailbreak">Jailbreak</option>
                    <option value="system_prompt_extraction">System Prompt Extraction</option>
                    <option value="role_manipulation">Role Manipulation</option>
                    <option value="context_poisoning">Context Poisoning</option>
                    <option value="instruction_override">Instruction Override</option>
                    <option value="tool_misuse">Tool Misuse</option>
                    <option value="sensitive_data_extraction">Sensitive Data Extraction</option>
                    <option value="policy_circumvention">Policy Circumvention</option>
                    <option value="output_format_manipulation">Output Format Manipulation</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="severity">Severity *</Label>
                  <Select value={severity} onValueChange={setSeverity}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </Select>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="tags">Tags (comma separated)</Label>
                <Input
                  id="tags"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="injection, security, safety"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Prompt Template</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="prompt-template">Prompt Template *</Label>
                <Textarea
                  id="prompt-template"
                  value={promptTemplate}
                  onChange={(e) => setPromptTemplate(e.target.value)}
                  placeholder="Enter the attack prompt template..."
                  rows={6}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="system-prompt-override">System Prompt Override</Label>
                <Textarea
                  id="system-prompt-override"
                  value={systemPromptOverride}
                  onChange={(e) => setSystemPromptOverride(e.target.value)}
                  placeholder="Optional: override the system prompt for this attack..."
                  rows={4}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expected-behavior">Expected Behavior</Label>
                <Textarea
                  id="expected-behavior"
                  value={expectedBehavior}
                  onChange={(e) => setExpectedBehavior(e.target.value)}
                  placeholder="What should a safe model do in response to this attack?"
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Severity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Badge className="w-full justify-center" variant={severity === "low" ? "default" : "secondary"}>
                  Low
                </Badge>
                <Badge className="w-full justify-center" variant={severity === "medium" ? "default" : "secondary"}>
                  Medium
                </Badge>
                <Badge className="w-full justify-center" variant={severity === "high" ? "default" : "secondary"}>
                  High
                </Badge>
                <Badge className="w-full justify-center" variant={severity === "critical" ? "default" : "secondary"}>
                  Critical
                </Badge>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Preview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md bg-muted p-3 text-sm">
                {promptTemplate || "Enter a prompt template to see a preview"}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href="/redteam/definitions">Cancel</Link>
        </Button>
        <Button onClick={handleSubmit} disabled={createMutation.isPending || !name || !promptTemplate}>
          <Plus className="mr-2 h-4 w-4" />
          {createMutation.isPending ? "Creating..." : "Create Attack Definition"}
        </Button>
      </div>
    </div>
  );
}