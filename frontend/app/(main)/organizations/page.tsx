"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Organization } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listOrganizations()
      .then((data) => {
        setOrganizations(data as Organization[]);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Organizations</h1>
        <Button>Create Organization</Button>
      </div>
      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : organizations.length === 0 ? (
        <Card>
          <CardContent className="text-muted-foreground py-8 text-center">
            No organizations yet. Create one to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {organizations.map((org) => (
            <Link key={org.id} href={`/organizations/${org.id}`}>
              <Card className="hover:bg-muted transition-colors">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {org.name}
                    {org.is_active ? (
                      <Badge variant="default">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground text-sm">
                    {org.description || "No description"}
                  </p>
                  <p className="text-muted-foreground mt-2 text-xs">Slug: {org.slug}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
