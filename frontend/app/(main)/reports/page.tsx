"use client";

import { Download, Shield } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const reportData = [
  { name: "Jan", passed: 85, violated: 5, failed: 2 },
  { name: "Feb", passed: 92, violated: 3, failed: 1 },
  { name: "Mar", passed: 78, violated: 8, failed: 4 },
  { name: "Apr", passed: 88, violated: 4, failed: 3 },
  { name: "May", passed: 91, violated: 2, failed: 1 },
  { name: "Jun", passed: 87, violated: 6, failed: 2 },
];

const safetyData = [
  { name: "Safe", value: 380, color: "#22c55e" },
  { name: "Suspicious", value: 45, color: "#eab308" },
  { name: "Violated", value: 23, color: "#ef4444" },
  { name: "Leaked", value: 5, color: "#dc2626" },
];

export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="text-muted-foreground">Evaluation and safety reports</p>
        </div>
        <Button variant="outline">
          <Download className="mr-2 h-4 w-4" />
          Export
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Evaluations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">24</div>
            <p className="text-xs text-muted-foreground">+12% from last month</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Safety Pass Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">93.2%</div>
            <p className="text-xs text-muted-foreground">-2.1% from last month</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Violations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">28</div>
            <p className="text-xs text-muted-foreground">+5 from last month</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Cost</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">$0.04</div>
            <p className="text-xs text-muted-foreground">Per item</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Evaluation Results Over Time</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reportData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="passed" name="Passed" fill="#22c55e" />
                  <Bar dataKey="violated" name="Violated" fill="#ef4444" />
                  <Bar dataKey="failed" name="Failed" fill="#6b7280" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Safety Verdict Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={safetyData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
                  >
                    {safetyData.map((entry, i) => (
                      <Cell key={`cell-${i}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Safety Reports</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center gap-4 rounded-md border p-4">
              <Shield className="h-8 w-8 text-green-500" />
              <div className="flex-1">
                <p className="font-medium">GPT-4 Safety Evaluation</p>
                <p className="text-sm text-muted-foreground">All safety dimensions passed</p>
              </div>
              <Badge className="bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400">
                Safe
              </Badge>
            </div>
            <div className="flex items-center gap-4 rounded-md border p-4">
              <Shield className="h-8 w-8 text-yellow-500" />
              <div className="flex-1">
                <p className="font-medium">Claude Jailbreak Attempt</p>
                <p className="text-sm text-muted-foreground">
                  Suspicious patterns detected in 3 scenarios
                </p>
              </div>
              <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-400">
                Suspicious
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
