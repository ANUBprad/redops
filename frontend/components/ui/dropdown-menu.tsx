import * as React from "react";
import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";

export interface DropdownMenuProps {
  trigger: React.ReactNode;
  items: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
    destructive?: boolean;
    disabled?: boolean;
  }[];
  align?: "start" | "center" | "end";
}

const DropdownMenu = React.forwardRef<HTMLDivElement, DropdownMenuProps>(
  ({ trigger, items, align = "end" }, _ref) => {
    const [open, setOpen] = React.useState(false);
    const containerRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
          setOpen(false);
        }
      };
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const alignment = {
      start: "origin-top-left",
      center: "origin-top-center",
      end: "origin-top-right",
    }[align];

    return (
      <div ref={containerRef} className="relative inline-block">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm hover:bg-accent"
        >
          {trigger}
          <ChevronDown className="h-4 w-4 opacity-50" />
        </button>
        {open && (
          <div
            className={cn(
              "absolute z-10 mt-1 min-w-[8rem] rounded-md border bg-popover text-popover-foreground shadow-md",
              alignment,
            )}
          >
            {items.map((item, i) => (
              <button
                key={i}
                type="button"
                disabled={item.disabled}
                onClick={() => {
                  item.onClick();
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent disabled:opacity-50",
                  item.destructive && "text-destructive hover:bg-destructive/10",
                )}
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  },
);
DropdownMenu.displayName = "DropdownMenu";

export { DropdownMenu };
