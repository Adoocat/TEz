// A row of mutually exclusive options (radio group), e.g. light / dark / system.
import { RadioGroup } from "radix-ui";

import { cn } from "@/lib/cn";

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
}

interface SegmentedProps<T extends string> {
  value: T;
  options: SegmentedOption<T>[];
  onValueChange: (value: T) => void;
  "aria-label": string;
  disabled?: boolean;
}

export function Segmented<T extends string>({
  value,
  options,
  onValueChange,
  disabled = false,
  ...aria
}: SegmentedProps<T>) {
  return (
    <RadioGroup.Root
      value={value}
      onValueChange={(next) => {
        const option = options.find((o) => o.value === next);
        if (option) onValueChange(option.value);
      }}
      disabled={disabled}
      orientation="horizontal"
      className="inline-flex rounded-md border border-line bg-surface p-0.5"
      {...aria}
    >
      {options.map((option) => (
        <RadioGroup.Item
          key={option.value}
          value={option.value}
          className={cn(
            "h-7 rounded-xs px-3 text-ui text-fg-muted transition-colors duration-[var(--motion-fast)]",
            "hover:text-fg data-[state=checked]:bg-raised data-[state=checked]:text-fg data-[state=checked]:shadow-popover",
          )}
        >
          {option.label}
        </RadioGroup.Item>
      ))}
    </RadioGroup.Root>
  );
}
