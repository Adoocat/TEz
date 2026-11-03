import type { ComponentProps } from "react";

import { cn } from "@/lib/cn";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      className={cn(
        "h-8 w-full rounded-md border border-line-strong bg-raised px-2.5 text-ui text-fg placeholder:text-fg-muted aria-invalid:border-danger",
        className,
      )}
      {...props}
    />
  );
}
