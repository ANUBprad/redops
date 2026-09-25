"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Plus, Shield, Search, Filter } from "lucide-react";

import { api } from "@/lib/api";
import type { Profile, ProfileCategory } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/loading-state";
import { Pagination } from "@/components/ui/pagination";

const CATEGORY_COLORS: Record<ProfileCategory, string> = {
  safety: "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400",
  quality: "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400",
  performance: "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400",
  cost: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400",
};

export default function ProfilesPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const { data, isLoading, error } = useQuery({
    queryKey: ["profiles", { search, category, page, page_size: pageSize }],
    queryFn: () =>
      api.listProfiles({
        search: search || undefined,
        category: category ?? undefined,
        page,
        page_size: pageSize,
      }),
  });

  const profiles = (data?.items ?? []) as Profile[];
  const total = data?.total ?? 0;

  if (isLoading) return <LoadingState />;

  if (error) {
    return (
      <div className="space-y-6">
        <div className="text-destructive">Failed to load profiles. Please try again.</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Profiles</h1>
          <p className="text-muted-foreground">
            Create and manage scoring profiles for metric weighting.
          </p>
        </div>
        <Button asChild>
          <Link href="/profiles/new">
            <Plus className="mr-2 h-4 w-4" />
            New Profile
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search profiles..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="pl-8"
          />
        </div>
        <Select
          value={category ?? "all"}
          onValueChange={(v) => {
            setCategory(v === "all" ? null : v);
            setPage(1);
          }}
        >
          <option value="all">All Categories</option>
          <option value="safety">Safety</option>
          <option value="quality">Quality</option>
          <option value="performance">Performance</option>
          <option value="cost">Cost</option>
        </Select>
        <Button variant="outline" size="sm">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      {profiles.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Shield className="mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">No profiles found.</p>
            <Button asChild className="mt-4">
              <Link href="/profiles/new">Create your first profile</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {profiles.map((profile) => (
            <Link key={profile.id} href={`/profiles/${profile.id}`}>
              <Card className="cursor-pointer transition-shadow hover:shadow-md">
                <CardContent className="flex items-center justify-between p-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="truncate font-semibold">{profile.name}</h3>
                      <Badge className={CATEGORY_COLORS[profile.category]}>
                        {profile.category}
                      </Badge>
                      {profile.is_default && <Badge variant="secondary">Default</Badge>}
                    </div>
                    {profile.description && (
                      <p className="mt-1 truncate text-sm text-muted-foreground">
                        {profile.description}
                      </p>
                    )}
                    <div className="mt-2 flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{Object.keys(profile.metric_overrides).length} metrics configured</span>
                      <span>{new Date(profile.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
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
