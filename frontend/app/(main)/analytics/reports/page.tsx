"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { FileText, Download, Shield, Target, BarChart3, AlertTriangle } from "lucide-react";
import type { GeneratedReport } from "@/types/api";

const REPORT_TYPES = [
  { value: "executive_summary", label: "Executive Summary", icon: BarChart3 },
  { value: "evaluation_report", label: "Evaluation Report", icon: Target },
  { value: "run_report", label: "Run Report", icon: FileText },
  { value: "safety_report", label: "Safety Report", icon: Shield },
  { value: "red_team_report", label: "Red Team Report", icon: AlertTriangle },
  { value: "comparison_report", label: "Comparison Report", icon: BarChart3 },
];

export default function ReportsPage() {
  const [reportType, setReportType] = useState("executive_summary");
  const [days, setDays] = useState(30);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["analytics", "report", reportType, days],
    queryFn: () =>
      api.generateReport({
        report_type: reportType,
        days,
      }) as Promise<GeneratedReport>,
    enabled: false,
  });

  const report = data ?? null;

  const handleExport = (format: string) => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.title.replace(/\s+/g, "_").toLowerCase()}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="text-muted-foreground">Generate and export analytics reports</p>
        </div>
        {report && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => handleExport("json")}>
              <Download className="mr-2 h-4 w-4" />
              Export JSON
            </Button>
          </div>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Generate Report</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <Label>Report Type</Label>
              <Select value={reportType} onValueChange={setReportType}>
                {REPORT_TYPES.map((rt) => (
                  <option key={rt.value} value={rt.value}>
                    {rt.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Time Range</Label>
              <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
                <option value="7">Last 7 days</option>
                <option value="14">Last 14 days</option>
                <option value="30">Last 30 days</option>
                <option value="90">Last 90 days</option>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>&nbsp;</Label>
              <Button className="w-full" onClick={() => refetch()} disabled={isLoading}>
                {isLoading ? "Generating..." : "Generate Report"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {report && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {report.title}
                </CardTitle>
                <Badge variant="outline">{report.report_type}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{report.description}</p>
              {report.generated_at && (
                <p className="text-xs text-muted-foreground">
                  Generated: {new Date(report.generated_at).toLocaleString()}
                </p>
              )}
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="mb-2 text-lg font-semibold">Summary</h3>
                <p className="text-sm text-muted-foreground">{report.summary}</p>
              </div>

              {Object.keys(report.statistics).length > 0 && (
                <div>
                  <h3 className="mb-2 text-lg font-semibold">Key Statistics</h3>
                  <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                    {Object.entries(report.statistics).map(([key, value]) => (
                      <div key={key} className="rounded-lg border p-3">
                        <div className="text-xs capitalize text-muted-foreground">
                          {key.replace(/_/g, " ")}
                        </div>
                        <div className="text-lg font-bold">
                          {typeof value === "number"
                            ? key.includes("cost")
                              ? `$${value.toFixed(4)}`
                              : key.includes("rate") || key.includes("score")
                                ? `${value.toFixed(1)}%`
                                : value.toLocaleString()
                            : value}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {report.sections.length > 0 && (
                <div>
                  <h3 className="mb-2 text-lg font-semibold">Sections</h3>
                  <div className="space-y-4">
                    {report.sections.map((section, idx) => (
                      <div key={idx} className="rounded-lg border p-4">
                        <h4 className="mb-2 font-medium">{section.title}</h4>
                        <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                          {section.content}
                        </p>
                        {Object.keys(section.statistics).length > 0 && (
                          <div className="mt-3 grid gap-2 md:grid-cols-3">
                            {Object.entries(section.statistics).map(([k, v]) => (
                              <div key={k} className="text-xs">
                                <span className="text-muted-foreground">{k}: </span>
                                <span className="font-medium">{v}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {report.recommendations.length > 0 && (
                <div>
                  <h3 className="mb-2 text-lg font-semibold">Recommendations</h3>
                  <ul className="space-y-2">
                    {report.recommendations.map((rec, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2 text-sm text-muted-foreground"
                      >
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {!report && !isLoading && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="mb-4 h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">
              Select a report type and click Generate to create a report
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
