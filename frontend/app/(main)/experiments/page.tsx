"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Plus, FlaskConical, Search, Filter } from "lucide-react";

import { api } from "@/lib/api";
import type { Experiment, ExperimentStatus } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import { Pagination } from "@/components/ui/pagination";

const STATUS_COLORS: Record<ExperimentStatus, string> = {
  draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
  active: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400",
  completed: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
  archived: "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400",
};

export default function ExperimentsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const { data, isLoading, error } = useQuery({
    queryKey: ["experiments", { search, status, page, page_size: pageSize }],
    queryFn: () =>
      api.listExperiments({
        search: search || undefined,
        status: status ?? undefined,
        page,
        page_size: pageSize,
      }),
  });

  const experiments = (data?.items ?? []) as Experiment[];
  const total = data?.total ?? 0;

  if (isLoading) return <LoadingState />;

  if (error) {
    return (
      <div className="space-y-6">
        <div className="text-destructive">Failed to load experiments. Please try again.</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Experiments</h1>
          <p className="text-muted-foreground">
            Design and track A/B experiments comparing models and configurations.
          </p>
        </div>
        <Button asChild>
          <Link href="/experiments/new">
            <Plus className="mr-2 h-4 w-4" />
            New Experiment
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search experiments..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-8"
          />
        </div>
        <Select
          value={status ?? "all"}
          onValueChange={(v) => {
            setStatus(v === "all" ? null : v);
            setPage(1);
          }}
        >
          <option value="all">All Status</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="archived">Archived</option>
        </Select>
        <Button variant="outline" size="sm">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      {experiments.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FlaskConical className="mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">No experiments found.</p>
            <Button asChild className="mt-4">
              <Link href="/experiments/new">Create your first experiment</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {experiments.map((exp) => (
            <Link key={exp.id} href={`/experiments/${exp.id}`}>
              <Card className="cursor-pointer transition-shadow hover:shadow-md">
                <CardContent className="flex items-center justify-between p-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="truncate font-semibold">{exp.name}</h3>
                      <Badge className={STATUS_COLORS[exp.status]}>{exp.status}</Badge>
                    </div>
                    {exp.description && (
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {exp.description}
                      </p>
                    )}
                    <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                      {exp.hypothesis && (
                        <span className="max-w-xs truncate">Hypothesis: {exp.hypothesis}</span>
                      )}
                      <span>{new Date(exp.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  {exp.tags.length > 0 && (
                    <div className="ml-4 flex flex-wrap gap-1">
                      {exp.tags.slice(0, 3).map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {total > pageSize && (
        <Pagination current={page} total={total} pageSize={pageSize} onPageChange={setPage} />
      )}
    </div>
  );
}
