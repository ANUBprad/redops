"use client";

import { useState, useMemo } from "react";
import { Plus, Search } from "lucide-react";
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

interface AttackDefinition {
  id: string;
  name: string;
  description: string;
  category: string;
  severity: string;
  status: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

const severityColors: Record<string, string> = {
  low: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
  high: "bg-orange-100 text-orange-800 dark:bg-orange-900/20 dark:text-orange-400",
  critical: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400",
};

export default function RedTeamDefinitionsPage() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ["attack-definitions", { search, category: categoryFilter, severity: severityFilter, page, pageSize }],
    queryFn: () =>
      api.listAttackDefinitions({
        search: search || undefined,
        category: categoryFilter ?? undefined,
        severity: severityFilter ?? undefined,
        page,
        page_size: pageSize,
        sort_by: "created_at",
        sort_order: "desc",
      }),
  });

  const definitions = useMemo(() => {
    return (data?.items ?? []) as AttackDefinition[];
  }, [data?.items]);

  if (isLoading) return <LoadingState />;
  if (error) return <div className="text-destructive">Error loading attack definitions</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Red Team Attack Definitions</h1>
          <p className="text-muted-foreground">
            Manage attack templates for LLM security testing
          </p>
        </div>
        <Button asChild>
          <Link href="/redteam/definitions/new">
            <Plus className="mr-2 h-4 w-4" />
            New Attack Definition
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative max-w-sm">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search attacks..."
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={categoryFilter ?? "all"} onValueChange={(v) => setCategoryFilter(v === "all" ? null : v)}>
          <option value="all">All Categories</option>
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
        <Select value={severityFilter ?? "all"} onValueChange={(v) => setSeverityFilter(v === "all" ? null : v)}>
          <option value="all">All Severities</option>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </Select>
      </div>

      <div className="space-y-2">
        {definitions.map((def_) => (
          <Link key={def_.id} href={`/redteam/definitions/${def_.id}`}>
            <Card className="cursor-pointer transition-shadow hover:shadow-md">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">{def_.name}</h3>
                    <p className="text-sm text-muted-foreground">{def_.description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={severityColors[def_.severity] ?? "bg-muted"}>{def_.severity}</Badge>
                    <Badge variant="outline">{def_.category}</Badge>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {def_.tags.map((tag) => (
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
