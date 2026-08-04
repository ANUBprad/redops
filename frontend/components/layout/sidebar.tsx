"use client";

import {
  BarChart3,
  Bot,
  FileText,
  LayoutDashboard,
  PlayCircle,
  Settings,
  Shield,
  Target,
  TrendingUp,
  Key,
  Bell,
  ClipboardList,
  Calendar,
  Building2,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  exact?: boolean;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: <LayoutDashboard className="h-5 w-5" /> },
  { label: "Organizations", href: "/organizations", icon: <Building2 className="h-5 w-5" /> },
  { label: "Projects", href: "/projects", icon: <FileText className="h-5 w-5" /> },
  { label: "Evaluations", href: "/evaluations", icon: <Target className="h-5 w-5" /> },
  { label: "Runs", href: "/runs", icon: <PlayCircle className="h-5 w-5" /> },
  { label: "Agents", href: "/agents/runs", icon: <Bot className="h-5 w-5" /> },
  { label: "Metrics", href: "/metrics", icon: <BarChart3 className="h-5 w-5" /> },
  { label: "Red Team", href: "/redteam/definitions", icon: <Shield className="h-5 w-5" /> },
  { label: "Analytics", href: "/analytics", icon: <TrendingUp className="h-5 w-5" /> },
  { label: "Schedules", href: "/schedules", icon: <Calendar className="h-5 w-5" /> },
  { label: "API Keys", href: "/api-keys", icon: <Key className="h-5 w-5" /> },
  { label: "Notifications", href: "/notifications", icon: <Bell className="h-5 w-5" /> },
  { label: "Audit Logs", href: "/audit", icon: <ClipboardList className="h-5 w-5" /> },
  { label: "Settings", href: "/settings", icon: <Settings className="h-5 w-5" /> },
];

export function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();

  return (
    <aside className="flex h-screen w-64 flex-col overflow-y-auto border-r bg-card">
      <div className="p-6">
        <h1 className="text-xl font-bold">RedOps Eval</h1>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {navItems.map((item) => {
          const isActive = item.exact ? pathname === item.href : pathname.startsWith(item.href);
          return (
            <Tooltip key={item.href} content={item.label} side="right">
              <Link
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            </Tooltip>
          );
        })}
      </nav>
      <div className="p-4">
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
          Sign Out
        </Button>
      </div>
    </aside>
  );
}
