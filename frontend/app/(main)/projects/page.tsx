"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Plus, FolderOpen, Search } from "lucide-react";

import { api } from "@/lib/api";
import type { Project, Organization } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { LoadingState } from "@/components/ui/loading-state";

export default function ProjectsPage() {
  const [search, setSearch] = useState("");
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);

  const { data: orgs, isLoading: orgsLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: () => api.listOrganizations(),
  });

  const organizations = (orgs ?? []) as Organization[];

  const effectiveOrgId = selectedOrgId ?? organizations[0]?.id ?? null;

  const { data, isLoading, error } = useQuery({
    queryKey: ["projects", effectiveOrgId],
    queryFn: () => api.listProjects(effectiveOrgId!),
    enabled: !!effectiveOrgId,
  });

  const projects = (data ?? []) as Project[];

  if (orgsLoading || isLoading) return <LoadingState />;

  if (error) {
    return (
      <div className="space-y-6">
        <div className="text-destructive">Failed to load projects. Please try again.</div>
      </div>
    );
  }

  const filteredProjects = search
    ? projects.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()))
    : projects;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Projects</h1>
          <p className="text-muted-foreground">
            Organize evaluations and runs into projects.
          </p>
        </div>
        <Button asChild disabled={!effectiveOrgId}>
          <Link href={effectiveOrgId ? `/projects/new?org=${effectiveOrgId}` : "#"}>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        {organizations.length > 1 && (
          <Select
            value={effectiveOrgId ?? ""}
            onValueChange={(v) => setSelectedOrgId(v || null)}
          >
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </Select>
        )}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search projects..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      {!effectiveOrgId ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FolderOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              No organizations found. Create an organization first.
            </p>
          </CardContent>
        </Card>
      ) : filteredProjects.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FolderOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {search ? "No projects match your search." : "No projects yet."}
            </p>
            {!search && (
              <Button asChild className="mt-4">
                <Link href={`/projects/new?org=${effectiveOrgId}`}>Create your first project</Link>
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredProjects.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}`}>
              <Card className="cursor-pointer transition-shadow hover:shadow-md">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {project.name}
                    {project.is_active !== false && (
                      <span className="text-xs font-normal text-green-600">Active</span>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    {project.description || "No description"}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
