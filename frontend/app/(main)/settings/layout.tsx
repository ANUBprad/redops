"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Key, Users, Bell, Shield, Database, Settings } from "lucide-react";

const settingsLinks = [
  { label: "General", href: "/settings", icon: <Settings className="h-4 w-4" /> },
  { label: "Provider Credentials", href: "/settings/providers", icon: <Key className="h-4 w-4" /> },
  { label: "Team Management", href: "/settings/team", icon: <Users className="h-4 w-4" /> },
  { label: "Notifications", href: "/settings/notifications", icon: <Bell className="h-4 w-4" /> },
  { label: "Security", href: "/settings/security", icon: <Shield className="h-4 w-4" /> },
  { label: "Data Retention", href: "/settings/retention", icon: <Database className="h-4 w-4" /> },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Settings</h1>
      <div className="flex flex-col gap-6 lg:flex-row">
        <nav className="shrink-0 lg:w-56">
          <div className="flex flex-col gap-1">
            {settingsLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  pathname === link.href
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                {link.icon}
                {link.label}
              </Link>
            ))}
          </div>
        </nav>
        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
}
