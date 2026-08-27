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
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  exact?: boolean;
}

interface NavGroup {
  heading: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    heading: "AI Workflows",
    items: [
      {
        label: "Mission Control",
        href: "/dashboard",
        icon: <LayoutDashboard className="h-5 w-5" />,
      },
      { label: "Evaluations", href: "/evaluations", icon: <Target className="h-5 w-5" /> },
      { label: "Evaluation Runs", href: "/runs", icon: <PlayCircle className="h-5 w-5" /> },
      { label: "Agent Runs", href: "/agents/runs", icon: <Bot className="h-5 w-5" /> },
      { label: "Red Team", href: "/redteam/definitions", icon: <Shield className="h-5 w-5" /> },
      { label: "Metrics", href: "/metrics", icon: <BarChart3 className="h-5 w-5" /> },
    ],
  },
  {
    heading: "Insights",
    items: [{ label: "Analytics", href: "/analytics", icon: <TrendingUp className="h-5 w-5" /> }],
  },
  {
    heading: "Platform",
    items: [
      { label: "Organizations", href: "/organizations", icon: <Building2 className="h-5 w-5" /> },
      { label: "Projects", href: "/projects", icon: <FileText className="h-5 w-5" /> },
      { label: "Schedules", href: "/schedules", icon: <Calendar className="h-5 w-5" /> },
      { label: "API Keys", href: "/api-keys", icon: <Key className="h-5 w-5" /> },
      { label: "Notifications", href: "/notifications", icon: <Bell className="h-5 w-5" /> },
      { label: "Audit Logs", href: "/audit", icon: <ClipboardList className="h-5 w-5" /> },
      { label: "Settings", href: "/settings", icon: <Settings className="h-5 w-5" /> },
    ],
  },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { logout } = useAuth();

  const navContent = (
    <>
      <div className="flex items-center justify-between p-6">
        <div>
          <h1 className="text-xl font-bold">RedOps</h1>
          <p className="text-xs text-muted-foreground">AI Evaluation Platform</p>
        </div>
        <Button variant="ghost" size="sm" className="lg:hidden" onClick={onClose}>
          <X className="h-5 w-5" />
        </Button>
      </div>
      <nav className="flex-1 space-y-4 px-3 overflow-y-auto">
        {navGroups.map((group) => (
          <div key={group.heading}>
            <h2 className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {group.heading}
            </h2>
            <div className="space-y-0.5">
              {group.items.map((item) => {
                const isActive = item.exact
                  ? pathname === item.href
                  : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onClose}
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
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="p-4">
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={logout}>
          Sign Out
        </Button>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex h-screen w-64 flex-col overflow-y-auto border-r bg-card">
        {navContent}
      </aside>

      {/* Mobile overlay */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="fixed inset-0 bg-black/50" onClick={onClose} />
          <aside className="fixed inset-y-0 left-0 z-50 w-64 flex flex-col bg-card shadow-xl">
            {navContent}
          </aside>
        </div>
      )}
    </>
  );
}
