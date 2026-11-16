import { useEffect, useRef } from "react";
import { defaultKeybindingsHandlerIgnore, tinykeys, type KeybindingsMap } from "tinykeys";

import { shortcutMaps, type Shortcut, type ShortcutContext, type ShortcutId } from "./maps";

export type ShortcutHandlers<C extends ShortcutContext> = Partial<
  Record<ShortcutId<C>, (event: KeyboardEvent) => void>
>;

/** Ignore typing in text fields (tinykeys' default) and, outside the global context, keys
 * pressed inside an open dialog, so a screen's letters never fire behind a dialog. */
export function shouldIgnore(event: KeyboardEvent, context: ShortcutContext): boolean {
  if (defaultKeybindingsHandlerIgnore(event)) return true;
  if (context === "global") return false;
  const target = event.target;
  return (
    target instanceof Element && target.closest('[role="dialog"],[role="alertdialog"]') !== null
  );
}

/** Bind a context's shortcuts to the window while the component is mounted (and enabled).
 * Only shortcuts with a handler are bound; a handled key does not reach the browser. */
export function useShortcuts<C extends ShortcutContext>(
  context: C,
  handlers: ShortcutHandlers<C>,
  { enabled = true }: { enabled?: boolean } = {},
): void {
  const latest = useRef(handlers);
  useEffect(() => {
    latest.current = handlers;
  });
  const bound = Object.keys(handlers).sort().join(",");

  useEffect(() => {
    if (!enabled) return;
    const bindings: KeybindingsMap = {};
    for (const { id, keys } of shortcutMaps[context] as readonly Shortcut[]) {
      if (!bound.split(",").includes(id)) continue;
      for (const key of keys) {
        bindings[key] = (event) => {
          const handler = (
            latest.current as Record<string, ((e: KeyboardEvent) => void) | undefined>
          )[id];
          if (!handler) return;
          event.preventDefault();
          handler(event);
        };
      }
    }
    return tinykeys(window, bindings, { ignore: (event) => shouldIgnore(event, context) });
  }, [context, bound, enabled]);
}
