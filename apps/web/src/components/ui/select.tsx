import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A plain, styled `<select>` rather than a Radix `Select` — Radix's
 * version needs its own `SelectTrigger`/`SelectContent`/`SelectItem`
 * composition, which isn't worth the extra dependency and component count
 * for the handful of plain option lists this app has so far (source type,
 * limit). Revisit if a picker needs search/multi-select/rich options.
 */
export type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>;

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(({ className, children, ...props }, ref) => {
  return (
    <select
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm " +
          "ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring " +
          "focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
});
Select.displayName = "Select";

export { Select };
