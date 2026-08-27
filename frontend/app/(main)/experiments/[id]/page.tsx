"use client";

import { useState } from "react";
import React from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Pencil, Trash2, Archive } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import type { Experiment } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";

export default function ExperimentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = React.use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editHypothesis, setEditHypothesis] = useState("");
  const [editMethodology, setEditMethodology] = useState("");
  const [editStatus, setEditStatus] = useState("");
  const [editTags, setEditTags] = useState("");

  const {
    data: experiment,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["experiment", id],
    queryFn: () => api.getExperiment(id),
  });

  const exp = experiment as Experiment | undefined;

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.updateExperiment(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiment", id] });
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
      setIsEditing(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteExperiment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
      router.push("/experiments");
    },
  });

  const archiveMutation = useMutation({
    mutationFn: () => api.archiveExperiment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiment", id] });
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
    },
  });

  const startEditing = () => {
    if (!exp) return;
    setEditName(exp.name);
    setEditDescription(exp.description ?? "");
    setEditHypothesis(exp.hypothesis ?? "");
    setEditMethodology(exp.methodology ?? "");
    setEditStatus(exp.status);
    setEditTags(exp.tags.join(", "));
    setIsEditing(true);
  };

  const saveChanges = () => {
    updateMutation.mutate({
      name: editName,
      description: editDescription || null,
      hypothesis: editHypothesis || null,
      methodology: editMethodology || null,
      status: editStatus,
      tags: editTags
        ? editTags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean)
        : [],
    });
  };

  if (isLoading) return <LoadingState />;

  if (error || !exp) {
    return (
      <div className="space-y-6">
        <div className="text-destructive">Experiment not found.</div>
      </div>
    );
  }

  const STATUS_COLORS: Record<string, string> = {
    draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
    active: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400",
    completed: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
    archived: "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400",
  };

  return (
    <div className="space-y-6">
      <div>
        <Link href="/experiments" className="text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-1 inline h-4 w-4" />
          Back to Experiments
        </Link>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{exp.name}</h1>
          <p className="text-muted-foreground">Experiment details and configuration</p>
        </div>
        <div className="flex items-center gap-2">
          {!isEditing ? (
            <>
              <Button variant="outline" size="sm" onClick={startEditing}>
                <Pencil className="mr-1 h-4 w-4" />
                Edit
              </Button>
              {exp.status !== "archived" && (
                <Button variant="outline" size="sm" onClick={() => archiveMutation.mutate()}>
                  <Archive className="mr-1 h-4 w-4" />
                  Archive
                </Button>
              )}
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  if (window.confirm("Delete this experiment? This cannot be undone.")) {
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
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label>Hypothesis</Label>
                <Textarea
                  value={editHypothesis}
                  onChange={(e) => setEditHypothesis(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label>Methodology</Label>
                <Textarea
                  value={editMethodology}
                  onChange={(e) => setEditMethodology(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select value={editStatus} onValueChange={setEditStatus}>
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="completed">Completed</option>
                    <option value="archived">Archived</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Tags (comma separated)</Label>
                  <Input value={editTags} onChange={(e) => setEditTags(e.target.value)} />
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <span className="font-medium">Status:</span>
                <Badge className={STATUS_COLORS[exp.status]}>{exp.status}</Badge>
              </div>
              {exp.description && (
                <div>
                  <span className="font-medium">Description:</span>
                  <p className="mt-1 text-muted-foreground">{exp.description}</p>
                </div>
              )}
              {exp.hypothesis && (
                <div>
                  <span className="font-medium">Hypothesis:</span>
                  <p className="mt-1 text-muted-foreground">{exp.hypothesis}</p>
                </div>
              )}
              {exp.methodology && (
                <div>
                  <span className="font-medium">Methodology:</span>
                  <p className="mt-1 text-muted-foreground">{exp.methodology}</p>
                </div>
              )}
              <div>
                <span className="font-medium">Tags:</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {exp.tags.length > 0 ? (
                    exp.tags.map((tag) => (
                      <Badge key={tag} variant="outline">
                        {tag}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">No tags</span>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground">
                <div>
                  <span className="font-medium text-foreground">Created:</span>{" "}
                  {new Date(exp.created_at).toLocaleString()}
                </div>
                <div>
                  <span className="font-medium text-foreground">Updated:</span>{" "}
                  {new Date(exp.updated_at).toLocaleString()}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
