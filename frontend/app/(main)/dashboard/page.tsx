import { BarChart3, Clock, FileText, PlayCircle, Shield, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const statCards = [
  {
    title: "Total Evaluations",
    value: "24",
    change: "+12%",
    icon: FileText,
    color: "text-blue-500",
  },
  { title: "Active Runs", value: "7", change: "+3", icon: PlayCircle, color: "text-green-500" },
  { title: "Total Runs", value: "156", change: "+24", icon: Clock, color: "text-purple-500" },
  { title: "Avg Score", value: "0.87", change: "+0.03", icon: BarChart3, color: "text-amber-500" },
  { title: "Security Alerts", value: "3", change: "-1", icon: Shield, color: "text-red-500" },
  {
    title: "Cost (30d)",
    value: "$1,234",
    change: "+12%",
    icon: TrendingUp,
    color: "text-teal-500",
  },
];

const recentRuns = [
  {
    id: "run-001",
    name: "GPT-4 Safety Eval",
    status: "completed",
    progress: 100,
    score: 0.92,
    duration: "12m",
  },
  {
    id: "run-002",
    name: "Claude Prompt Injection",
    status: "running",
    progress: 68,
    score: 0.78,
    duration: "8m",
  },
  {
    id: "run-003",
    name: "Anthropic Red Team",
    status: "failed",
    progress: 45,
    score: 0.45,
    duration: "5m",
  },
  {
    id: "run-004",
    name: "Gemini Eval Batch",
    status: "completed",
    progress: 100,
    score: 0.88,
    duration: "22m",
  },
];

const getStatusColor = (status: string) => {
  switch (status) {
    case "completed":
      return "bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-400";
    case "running":
      return "bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-400";
    case "failed":
      return "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-400";
    default:
      return "bg-muted text-muted-foreground";
  }
};

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Overview of your evaluation platform</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {statCards.map((card) => (
          <Card key={card.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
              <card.icon className={`h-4 w-4 ${card.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
              <p className="text-xs text-muted-foreground">{card.change}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentRuns.map((run) => (
                <div key={run.id} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{run.name}</span>
                    <Badge className={getStatusColor(run.status)}>{run.status}</Badge>
                  </div>
                  <Progress value={run.progress} className="h-2" />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{run.progress}% complete</span>
                    <span>
                      Score: {run.score.toFixed(2)} · {run.duration}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Safety Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm">Prompt Injection</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-green-600">98% Safe</span>
                </div>
              </div>
              <Progress value={98} className="h-2" />
              <div className="flex items-center justify-between">
                <span className="text-sm">Jailbreak Attempts</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-red-600">12% Violated</span>
                </div>
              </div>
              <Progress value={12} className="h-2" />
              <div className="flex items-center justify-between">
                <span className="text-sm">Data Extraction</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-green-600">95% Safe</span>
                </div>
              </div>
              <Progress value={95} className="h-2" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
