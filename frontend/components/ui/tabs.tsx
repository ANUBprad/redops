"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface TabsProps {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  tabs: { value: string; label: string; icon?: React.ReactNode }[];
  children: React.ReactNode;
}

const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
  ({ defaultValue, value, onValueChange, tabs, children }, ref) => {
    const [active, setActive] = React.useState(value ?? defaultValue ?? tabs[0]?.value ?? "");

    React.useEffect(() => {
      if (value !== undefined) {
        setActive(value);
      }
    }, [value]);

    const handleChange = (val: string) => {
      setActive(val);
      onValueChange?.(val);
    };

    return (
      <div ref={ref} className="w-full">
        <div className="border-b">
          <nav className="-mb-px flex space-x-8 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => handleChange(tab.value)}
                className={cn(
                  "flex items-center gap-2 border-b-2 border-transparent px-1 py-3 text-sm font-medium",
                  active === tab.value && "border-primary text-primary",
                  active !== tab.value && "text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
        <div className="pt-4">{children}</div>
      </div>
    );
  },
);
Tabs.displayName = "Tabs";

export { Tabs };
