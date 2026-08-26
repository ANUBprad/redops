"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { NotificationEntry } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listNotifications("current-org")
      .then((data) => {
        const d = data as { items: NotificationEntry[] };
        setNotifications(d.items ?? []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Notifications</h1>
      <Card>
        <CardHeader>
          <CardTitle>Recent Notifications</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-muted-foreground">Loading...</p>
          ) : notifications.length === 0 ? (
            <p className="text-muted-foreground">No notifications yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notifications.map((n) => (
                  <TableRow key={n.notification_id}>
                    <TableCell className="font-medium">{n.title}</TableCell>
                    <TableCell>{n.channel}</TableCell>
                    <TableCell>{n.event}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          n.status === "sent"
                            ? "default"
                            : n.status === "failed"
                              ? "destructive"
                              : "secondary"
                        }
                      >
                        {n.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{new Date(n.timestamp).toLocaleString()}</TableCell>
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
