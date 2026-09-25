"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus, X } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";

export default function NewProfilePage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("safety");
  const [isDefault, setIsDefault] = useState(false);
  const [metricName, setMetricName] = useState("");
  const [metricWeight, setMetricWeight] = useState("1.0");
  const [metricEnabled, setMetricEnabled] = useState(true);
  const [overrides, setOverrides] = useState<
    Record<string, { weight: number; enabled: boolean; parameters: Record<string, unknown> }>
  >({});

  const addMetric = () => {
    if (!metricName.trim()) return;
    setOverrides((prev) => ({
      ...prev,
      [metricName.trim()]: {
        weight: parseFloat(metricWeight) || 1.0,
        enabled: metricEnabled,
        parameters: {},
      },
    }));
    setMetricName("");
    setMetricWeight("1.0");
    setMetricEnabled(true);
  };

  const removeMetric = (name: string) => {
    setOverrides((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  const createMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      router.push("/profiles");
    },
  });

  const handleSubmit = () => {
    createMutation.mutate({
      name,
      description: description || undefined,
      category,
      is_default: isDefault,
      metric_overrides: overrides,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <Link href="/profiles" className="text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-1 inline h-4 w-4" />
          Back to Profiles
        </Link>
        <h1 className="mt-2 text-3xl font-bold">New Profile</h1>
        <p className="text-muted-foreground">
          Create a scoring profile with custom metric weights.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Safety-First Profile"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this profile optimize for?"
              rows={2}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="category">Category</Label>
              <Select value={category} onValueChange={setCategory}>
                <option value="safety">Safety</option>
                <option value="quality">Quality</option>
                <option value="performance">Performance</option>
                <option value="cost">Cost</option>
              </Select>
            </div>
            <div className="flex items-end space-y-2 pb-1">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={isDefault}
                  onChange={(e) => setIsDefault(e.target.checked)}
                  className="rounded border-input"
                />
                Set as default for this category
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metric Overrides</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-[1fr_100px_100px_40px] items-end gap-2">
            <div className="space-y-2">
              <Label>Metric Name</Label>
              <Input
                value={metricName}
                onChange={(e) => setMetricName(e.target.value)}
                placeholder="e.g. correctness"
              />
            </div>
            <div className="space-y-2">
              <Label>Weight</Label>
              <Input
                type="number"
                value={metricWeight}
                onChange={(e) => setMetricWeight(e.target.value)}
                min="0"
                step="0.1"
              />
            </div>
            <div className="flex items-end space-y-2 pb-1">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={metricEnabled}
                  onChange={(e) => setMetricEnabled(e.target.checked)}
                  className="rounded border-input"
                />
                Enabled
              </label>
            </div>
            <Button variant="outline" size="sm" onClick={addMetric}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          {Object.keys(overrides).length > 0 && (
            <div className="mt-4 space-y-2">
              {Object.entries(overrides).map(([metric, config]) => (
                <div key={metric} className="flex items-center justify-between rounded border p-2">
                  <div className="flex items-center gap-3">
                    <Badge variant="outline">{metric}</Badge>
                    <span className="text-sm text-muted-foreground">Weight: {config.weight}</span>
                    {!config.enabled && <Badge variant="secondary">Disabled</Badge>}
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => removeMetric(metric)}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => router.push("/profiles")}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={createMutation.isPending || !name.trim()}>
              {createMutation.isPending ? "Creating..." : "Create Profile"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
