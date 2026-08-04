"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ApiKeyInfo } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listApiKeys().then((data) => {
      setKeys(data as ApiKeyInfo[]);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">API Keys</h1>
        <Button>Create API Key</Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : keys.length === 0 ? (
            <p className="text-muted-foreground">No API keys created yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Prefix</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Last Used</TableHead>
                  <TableHead>Expires</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="font-medium">{k.name}</TableCell>
                    <TableCell className="font-mono text-xs">{k.prefix}...</TableCell>
                    <TableCell>
                      <Badge variant={k.is_active ? "default" : "destructive"}>
                        {k.is_active ? "Active" : "Revoked"}
                      </Badge>
                    </TableCell>
                    <TableCell>{k.usage_count}</TableCell>
                    <TableCell>{k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : "Never"}</TableCell>
                    <TableCell>{k.expires_at ? new Date(k.expires_at).toLocaleDateString() : "Never"}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => api.revokeApiKey(k.id)}>
                        Revoke
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
