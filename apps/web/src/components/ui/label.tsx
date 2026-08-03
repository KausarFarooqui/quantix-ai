import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * A plain `<label>` rather than `@radix-ui/react-label` — Radix's version
 * only adds text-selection prevention on double-click, which isn't worth
 * a new dependency for this milestone. Revisit if a form needs its extra
 * `asChild`/composition behavior.
 */
const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className,
      )}
      {...props}
    />
  ),
);
Label.displayName = "Label";

export { Label };
