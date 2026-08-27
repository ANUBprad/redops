"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";

export default function NewExperimentPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [methodology, setMethodology] = useState("");
  const [status, setStatus] = useState("draft");
  const [tags, setTags] = useState("");

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createExperiment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
      router.push("/experiments");
    },
  });

  const handleSubmit = () => {
    createMutation.mutate({
      name,
      description: description || undefined,
      hypothesis: hypothesis || undefined,
      methodology: methodology || undefined,
      status,
      tags: tags
        ? tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean)
        : [],
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <Link href="/experiments" className="text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-1 inline h-4 w-4" />
          Back to Experiments
        </Link>
        <h1 className="mt-2 text-3xl font-bold">New Experiment</h1>
        <p className="text-muted-foreground">
          Create a new experiment to compare models and configurations.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Experiment Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. GPT-4o vs Claude 3.5 Safety Comparison"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this experiment about?"
              rows={3}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="hypothesis">Hypothesis</Label>
            <Textarea
              id="hypothesis"
              value={hypothesis}
              onChange={(e) => setHypothesis(e.target.value)}
              placeholder="What do you expect to find?"
              rows={2}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="methodology">Methodology</Label>
            <Textarea
              id="methodology"
              value={methodology}
              onChange={(e) => setMethodology(e.target.value)}
              placeholder="How will you test this hypothesis?"
              rows={2}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
              <Select value={status} onValueChange={setStatus}>
                <option value="draft">Draft</option>
                <option value="active">Active</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="tags">Tags (comma separated)</Label>
              <Input
                id="tags"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="safety, comparison"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => router.push("/experiments")}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={createMutation.isPending || !name.trim()}>
              {createMutation.isPending ? "Creating..." : "Create Experiment"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
