import { useState, useEffect, useCallback } from "react";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Dialog } from "@/components/ui/dialog";
import { useRouter } from "next/navigation";
import { BarChart3, FileText, LayoutDashboard, PlayCircle, Shield, Target } from "lucide-react";

const commands = [
  { label: "Dashboard", href: "/dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { label: "Projects", href: "/projects", icon: <FileText className="h-4 w-4" /> },
  { label: "Evaluations", href: "/evaluations", icon: <Target className="h-4 w-4" /> },
  { label: "Runs", href: "/runs", icon: <PlayCircle className="h-4 w-4" /> },
  { label: "Metrics", href: "/metrics", icon: <BarChart3 className="h-4 w-4" /> },
  { label: "Red Team", href: "/redteam/definitions", icon: <Shield className="h-4 w-4" /> },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const handleSelect = useCallback((href: string) => {
    setOpen(false);
    router.push(href);
  }, [router]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Command className="p-0 shadow-xl max-w-md">
        <CommandInput placeholder="Type to search..." />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup>
            {commands.map((cmd) => (
              <CommandItem
                key={cmd.href}
                onSelect={() => handleSelect(cmd.href)}
                className="flex items-center gap-2"
              >
                {cmd.icon}
                {cmd.label}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </Dialog>
  );
}
