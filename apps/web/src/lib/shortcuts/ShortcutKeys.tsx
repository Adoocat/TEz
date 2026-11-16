import { cn } from "@/lib/cn";

import { ariaBinding, shortcutLabels } from "./keys";
import { shortcut, type ShortcutContext, type ShortcutId } from "./maps";

/** The `kbd` hint of a shortcut, from its context's map (a button's "I", the overlay's
 * "⌘1 … ⌘7"). */
export function ShortcutKeys<C extends ShortcutContext>({
  context,
  id,
  className,
}: {
  context: C;
  id: ShortcutId<C>;
  className?: string;
}) {
  const definition = shortcut(context, id);
  const labels = shortcutLabels(definition);
  const separator = definition.display === "range" ? "…" : "·";
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      {labels.map((label, index) => (
        <span key={label} className="inline-flex items-center gap-1">
          {index > 0 && (
            <span aria-hidden className="text-fg-muted">
              {separator}
            </span>
          )}
          <kbd className="rounded-xs border border-kbd-line bg-kbd px-1.5 font-mono text-meta">
            {label}
          </kbd>
        </span>
      ))}
    </span>
  );
}

/** The `aria-keyshortcuts` value of a shortcut, for the button that does the same thing. */
export function ariaShortcut<C extends ShortcutContext>(context: C, id: ShortcutId<C>): string {
  return shortcut(context, id)
    .keys.map((key) => ariaBinding(key))
    .join(" ");
}
