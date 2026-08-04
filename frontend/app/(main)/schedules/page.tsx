"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ScheduleInfo } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<ScheduleInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listSchedules().then((data) => {
      setSchedules(data as ScheduleInfo[]);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Schedules</h1>
        <Button>Create Schedule</Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Recurring Tasks</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : schedules.length === 0 ? (
            <p className="text-muted-foreground">No schedules configured.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Cron</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Runs</TableHead>
                  <TableHead>Failures</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedules.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell>{s.schedule_type}</TableCell>
                    <TableCell className="font-mono text-xs">{s.cron_expression}</TableCell>
                    <TableCell>
                      <Badge variant={s.status === "active" ? "default" : "secondary"}>
                        {s.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{s.run_count}</TableCell>
                    <TableCell>{s.failure_count}</TableCell>
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
