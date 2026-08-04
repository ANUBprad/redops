"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}

const Tooltip = React.forwardRef<HTMLSpanElement, TooltipProps>(
  ({ content, children, side = "top" }, _ref) => {
    const [visible, setVisible] = React.useState(false);
    const containerRef = React.useRef<HTMLSpanElement>(null);

    const positionClass = {
      top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
      right: "left-full top-1/2 -translate-y-1/2 ml-2",
      bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
      left: "right-full top-1/2 -translate-y-1/2 mr-2",
    }[side];

    return (
      <span ref={containerRef} className="relative inline-block" onMouseEnter={() => setVisible(true)} onMouseLeave={() => setVisible(false)}>
        {children}
        {visible && (
          <span
            className={cn(
              "pointer-events-none absolute z-10 rounded-md bg-popover px-2 py-1 text-xs text-popover-foreground shadow-md",
              positionClass,
            )}
          >
            {content}
          </span>
        )}
      </span>
    );
  },
);
Tooltip.displayName = "Tooltip";

export { Tooltip };
