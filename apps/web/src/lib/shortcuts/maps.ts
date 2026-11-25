// One shortcut map per context (design-prompt §6). Handlers, the `?` overlay and the `kbd`
// hints on buttons all read these maps, so a key is defined in exactly one place.
//
// Keys use tinykeys syntax and match `event.key` (case-insensitive), so a letter follows the
// keyboard layout: on a Turkish Q keyboard `i` is the key that types "i". `$mod` is ⌘ on
// Apple systems and Ctrl elsewhere.

export type ShortcutContext = "global" | "screening" | "reader" | "list";

export interface Shortcut {
  readonly id: string;
  /** Bindings that run the action; the overlay and hints show them in this order. */
  readonly keys: readonly string[];
  /** `range` shows the first and last key ("⌘1 … ⌘7") instead of each. */
  readonly display?: "range";
}

const digits = (prefix: string, last: number) =>
  Array.from({ length: last }, (_, n) => `${prefix}${String(n + 1)}`);

export const shortcutMaps = {
  global: [
    { id: "help", keys: ["[Shift]+?"] },
    { id: "goTo", keys: digits("$mod+", 7), display: "range" },
  ],
  screening: [
    { id: "include", keys: ["i"] },
    { id: "exclude", keys: ["e"] },
    { id: "reason", keys: digits("", 9), display: "range" },
    { id: "maybe", keys: ["m"] },
    { id: "skip", keys: ["ArrowRight"] },
    { id: "undo", keys: ["u"] },
    { id: "note", keys: ["n"] },
    { id: "next", keys: ["j"] },
    { id: "previous", keys: ["k"] },
  ],
  reader: [
    { id: "nextPage", keys: ["j"] },
    { id: "previousPage", keys: ["k"] },
    { id: "highlight", keys: ["h"] },
    { id: "find", keys: ["$mod+f"] },
    { id: "focusMode", keys: ["f"] },
  ],
  list: [
    { id: "down", keys: ["ArrowDown"] },
    { id: "up", keys: ["ArrowUp"] },
    { id: "preview", keys: ["Space"] },
    { id: "open", keys: ["Enter"] },
  ],
} as const satisfies Record<ShortcutContext, readonly Shortcut[]>;

export type ShortcutMaps = typeof shortcutMaps;
export type ShortcutId<C extends ShortcutContext> = ShortcutMaps[C][number]["id"];

export const shortcutContexts = Object.keys(shortcutMaps) as ShortcutContext[];

export function shortcut<C extends ShortcutContext>(context: C, id: ShortcutId<C>): Shortcut {
  const found = (shortcutMaps[context] as readonly Shortcut[]).find((s) => s.id === id);
  if (!found) throw new Error(`unknown shortcut ${context}.${id}`);
  return found;
}
