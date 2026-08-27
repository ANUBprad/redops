"use client";

import { useState } from "react";
import React from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pencil, Trash2, X, Plus } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import type { Profile, MetricOverride } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";

export default function ProfileDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editIsDefault, setEditIsDefault] = useState(false);
  const [editOverrides, setEditOverrides] = useState<Record<string, MetricOverride>>({});
  const [newMetricName, setNewMetricName] = useState("");
  const [newMetricWeight, setNewMetricWeight] = useState("1.0");

  const {
    data: profile,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["profile", id],
    queryFn: () => api.getProfile(id),
  });

  const p = profile as Profile | undefined;

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.updateProfile(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile", id] });
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      setIsEditing(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteProfile(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profiles"] });
      router.push("/profiles");
    },
  });

  const startEditing = () => {
    if (!p) return;
    setEditName(p.name);
    setEditDescription(p.description ?? "");
    setEditCategory(p.category);
    setEditIsDefault(p.is_default);
    setEditOverrides({ ...p.metric_overrides });
    setIsEditing(true);
  };

  const saveChanges = () => {
    updateMutation.mutate({
      name: editName,
      description: editDescription || null,
      category: editCategory,
      is_default: editIsDefault,
      metric_overrides: editOverrides,
    });
  };

  const addEditMetric = () => {
    if (!newMetricName.trim()) return;
    setEditOverrides((prev) => ({
      ...prev,
      [newMetricName.trim()]: {
        weight: parseFloat(newMetricWeight) || 1.0,
        enabled: true,
        parameters: {},
      },
    }));
    setNewMetricName("");
    setNewMetricWeight("1.0");
  };

  const removeEditMetric = (name: string) => {
    setEditOverrides((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  };

  if (isLoading) return <LoadingState />;

  if (error || !p) {
    return (
      <div className="space-y-6">
        <div className="text-destructive">Profile not found.</div>
      </div>
    );
  }

  const CATEGORY_COLORS: Record<string, string> = {
    safety: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400",
    quality: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
    performance: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400",
    cost: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
  };

  return (
    <div className="space-y-6">
      <div>
        <Link href="/profiles" className="text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-1 inline h-4 w-4" />
          Back to Profiles
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{p.name}</h1>
          <p className="text-muted-foreground">Profile configuration and metric weights</p>
        </div>
        <div className="flex items-center gap-2">
          {!isEditing ? (
            <>
              <Button variant="outline" size="sm" onClick={startEditing}>
                <Pencil className="mr-1 h-4 w-4" />
                Edit
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  if (window.confirm("Delete this profile? This cannot be undone.")) {
                    deleteMutation.mutate();
                  }
                }}
              >
                <Trash2 className="mr-1 h-4 w-4" />
                Delete
              </Button>
            </>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={saveChanges} disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Saving..." : "Save"}
              </Button>
            </>
          )}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isEditing ? (
            <>
              <div className="space-y-2">
                <Label>Name</Label>
                <Input value={editName} onChange={(e) => setEditName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Select value={editCategory} onValueChange={setEditCategory}>
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
                      checked={editIsDefault}
                      onChange={(e) => setEditIsDefault(e.target.checked)}
                      className="rounded border-input"
                    />
                    Set as default
                  </label>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <span className="font-medium">Category:</span>
                <Badge className={CATEGORY_COLORS[p.category]}>{p.category}</Badge>
                {p.is_default && <Badge variant="secondary">Default</Badge>}
              </div>
              {p.description && (
                <div>
                  <span className="font-medium">Description:</span>
                  <p className="mt-1 text-muted-foreground">{p.description}</p>
                </div>
              )}
              <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground">
                <div>
                  <span className="font-medium text-foreground">Created:</span>{" "}
                  {new Date(p.created_at).toLocaleString()}
                </div>
                <div>
                  <span className="font-medium text-foreground">Updated:</span>{" "}
                  {new Date(p.updated_at).toLocaleString()}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Metric Overrides</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isEditing && (
            <div className="grid grid-cols-[1fr_100px_40px] items-end gap-2">
              <div className="space-y-2">
                <Label>Metric Name</Label>
                <Input
                  value={newMetricName}
                  onChange={(e) => setNewMetricName(e.target.value)}
                  placeholder="e.g. correctness"
                />
              </div>
              <div className="space-y-2">
                <Label>Weight</Label>
                <Input
                  type="number"
                  value={newMetricWeight}
                  onChange={(e) => setNewMetricWeight(e.target.value)}
                  min="0"
                  step="0.1"
                />
              </div>
              <Button variant="outline" size="sm" onClick={addEditMetric}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          )}

          {Object.keys(isEditing ? editOverrides : p.metric_overrides).length === 0 ? (
            <p className="text-sm text-muted-foreground">No metric overrides configured.</p>
          ) : (
            <div className="space-y-2">
              {Object.entries(isEditing ? editOverrides : p.metric_overrides).map(
                ([metric, config]) => (
                  <div
                    key={metric}
                    className="flex items-center justify-between rounded border p-2"
                  >
                    <div className="flex items-center gap-3">
                      <Badge variant="outline">{metric}</Badge>
                      <span className="text-sm text-muted-foreground">Weight: {config.weight}</span>
                      {!config.enabled && <Badge variant="secondary">Disabled</Badge>}
                    </div>
                    {isEditing && (
                      <Button variant="ghost" size="sm" onClick={() => removeEditMetric(metric)}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ),
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
