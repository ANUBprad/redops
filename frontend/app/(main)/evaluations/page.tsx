"use client";

import { useMemo, useState } from "react";
import { Plus, Search, Filter } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { LoadingState } from "@/components/ui/loading-state";
import { Pagination } from "@/components/ui/pagination";

export default function EvaluationsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ["evaluations", { search, status: statusFilter, page, pageSize }],
    queryFn: () =>
      api.listEvaluations({
        search: search || undefined,
        status: statusFilter ?? undefined,
        page,
        page_size: pageSize,
        sort_by: "created_at",
        sort_order: "desc",
      }),
  });

  const evaluations = useMemo(() => {
    return (data?.items ?? []) as Array<{
      id: string;
      name: string;
      provider: string;
      model: string;
      status: string;
      tags: string[];
      metrics: string[];
      created_at: string;
      updated_at: string;
    }>;
  }, [data?.items]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
      case "ready":
        return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
      case "draft":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400";
      case "archived":
        return "bg-gray-100 text-gray-800 dark:bg-gray-900/20 dark:text-gray-400";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  if (isLoading) return <LoadingState />;
  if (error) return <div className="text-destructive">Error loading evaluations</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Evaluations</h1>
          <p className="text-muted-foreground">Manage your evaluation definitions</p>
        </div>
        <Button asChild>
          <Link href="/evaluations/new">
            <Plus className="mr-2 h-4 w-4" />
            New Evaluation
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search evaluations..."
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={statusFilter ?? "all"} onValueChange={(v) => setStatusFilter(v === "all" ? null : v)}>
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
        </Select>
        <Button variant="outline" size="sm">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-2">
        {evaluations.map((eval_) => (
          <Link key={eval_.id} href={`/evaluations/${eval_.id}`}>
            <Card className="cursor-pointer transition-shadow hover:shadow-md">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">{eval_.name}</h3>
                    <p className="text-sm text-muted-foreground">
                      {eval_.provider} · {eval_.model}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={getStatusColor(eval_.status)}>{eval_.status}</Badge>
                    <Badge variant="secondary">{eval_.metrics.length} metrics</Badge>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {eval_.tags.map((tag) => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {data && data.total > 0 && (
        <Pagination
          current={data.page}
          total={data.total}
          pageSize={data.page_size}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
