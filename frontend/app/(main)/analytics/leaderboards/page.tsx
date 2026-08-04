"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Trophy, Medal, TrendingUp, Zap, DollarSign, Shield } from "lucide-react";
import type { Leaderboard } from "@/types/api";

function getRankIcon(rank: number) {
  if (rank === 1) return <Trophy className="h-5 w-5 text-yellow-500" />;
  if (rank === 2) return <Medal className="h-5 w-5 text-gray-400" />;
  if (rank === 3) return <Medal className="h-5 w-5 text-amber-600" />;
  return <span className="text-sm font-medium text-muted-foreground w-5 text-center">{rank}</span>;
}

function getRankingIcon(rankingBy: string) {
  switch (rankingBy) {
    case "score": return <TrendingUp className="h-4 w-4" />;
    case "latency": return <Zap className="h-4 w-4" />;
    case "cost": return <DollarSign className="h-4 w-4" />;
    case "reliability": return <Shield className="h-4 w-4" />;
    default: return <TrendingUp className="h-4 w-4" />;
  }
}

export default function LeaderboardsPage() {
  const [rankingBy, setRankingBy] = useState("score");
  const [days, setDays] = useState(30);

  const { data, isLoading } = useQuery({
    queryKey: ["analytics", "leaderboard", rankingBy, days],
    queryFn: () =>
      api.getLeaderboard({
        ranking_by: rankingBy,
        days,
        limit: 10,
      }) as Promise<Leaderboard>,
  });

  const leaderboard = data ?? { title: "Leaderboard", ranking_by: rankingBy, entries: [] };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Leaderboards</h1>
        <p className="text-muted-foreground">
          Rank models and providers by performance metrics
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label>Ranking By</Label>
          <Select
            value={rankingBy}
            onValueChange={setRankingBy}
          >
            <option value="score">Overall Score</option>
            <option value="latency">Lowest Latency</option>
            <option value="cost">Lowest Cost</option>
            <option value="reliability">Most Reliable</option>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Time Range</Label>
          <Select
            value={String(days)}
            onValueChange={(v) => setDays(Number(v))}
          >
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          {getRankingIcon(leaderboard.ranking_by)}
          <CardTitle>{leaderboard.title}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              Loading leaderboard...
            </div>
          ) : leaderboard.entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Medal className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No data available for this ranking</p>
            </div>
          ) : (
            <div className="space-y-3">
              {leaderboard.entries.map((entry) => (
                <div
                  key={entry.entity_id}
                  className={`flex items-center justify-between p-4 rounded-lg border ${
                    entry.rank <= 3
                      ? "border-yellow-200 bg-yellow-50/50 dark:border-yellow-900/30 dark:bg-yellow-900/5"
                      : "border-border"
                  }`}
                >
                  <div className="flex items-center gap-4">
                    {getRankIcon(entry.rank)}
                    <div>
                      <div className="font-medium">{entry.entity_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {entry.metadata?.provider && `Provider: ${entry.metadata.provider}`}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold">
                      {entry.metric_name === "cost"
                        ? `$${entry.score.toFixed(4)}`
                        : entry.metric_name === "latency"
                          ? `${entry.score.toFixed(0)}ms`
                          : `${entry.score.toFixed(2)}%`}
                    </div>
                    <Badge variant="outline" className="text-xs">
                      {entry.metric_name}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
