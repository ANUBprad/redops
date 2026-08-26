"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function SettingsPage() {
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings</h1>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Notifications</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Email Notifications</span>
              <Badge variant="default">Enabled</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Slack Notifications</span>
              <Badge variant="secondary">Configure</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Webhook Notifications</span>
              <Badge variant="secondary">Configure</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Security</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Two-Factor Authentication</span>
              <Badge variant="secondary">Not configured</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Session Timeout</span>
              <span className="text-sm text-muted-foreground">24 hours</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">API Key Rotation</span>
              <Badge variant="default">90 days</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Data Retention</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Audit Log Retention</span>
              <span className="text-sm text-muted-foreground">Indefinite</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Evaluation Data</span>
              <span className="text-sm text-muted-foreground">Indefinite</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>RBAC</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">Owner</span>
              <span className="text-xs text-muted-foreground">Full access</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Admin</span>
              <span className="text-xs text-muted-foreground">Manage members & resources</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Developer</span>
              <span className="text-xs text-muted-foreground">Create & run evaluations</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Analyst</span>
              <span className="text-xs text-muted-foreground">Read & export reports</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">Viewer</span>
              <span className="text-xs text-muted-foreground">Read-only access</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSave}>{saved ? "Saved!" : "Save Settings"}</Button>
        <Button variant="outline">Reset</Button>
      </div>
    </div>
  );
}
