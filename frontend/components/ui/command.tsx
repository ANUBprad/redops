import * as React from "react";
import { cn } from "@/lib/utils";
import { Search } from "lucide-react";

const Command = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "bg-popover text-popover-foreground flex h-full flex-col overflow-hidden rounded-md",
        className,
      )}
      {...props}
    />
  ),
);
Command.displayName = "Command";

const CommandInput = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <div className="flex items-center border-b px-3">
    <Search className="h-4 w-4 shrink-0 opacity-50" />
    <input
      ref={ref}
      className={cn(
        "flex h-11 w-full border-none bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  </div>
));
CommandInput.displayName = "CommandInput";

const CommandList = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("overflow-y-auto overflow-x-hidden", className)} {...props} />
  ),
);
CommandList.displayName = "CommandList";

const CommandEmpty = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("py-6 text-center text-sm", className)} {...props} />
  ),
);
CommandEmpty.displayName = "CommandEmpty";

const CommandGroup = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("overflow-y-auto py-1", className)} {...props} />
  ),
);
CommandGroup.displayName = "CommandGroup";

const CommandItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { onSelect?: () => void }
>(({ className, onSelect, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex cursor-pointer items-center rounded-sm px-2 py-2 text-sm",
      "hover:bg-accent hover:text-accent-foreground",
      className,
    )}
    onClick={onSelect}
    {...props}
  />
));
CommandItem.displayName = "CommandItem";

export { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem };
