// Reading and showing keybindings: duplicate detection and platform-aware labels.
import type { Shortcut } from "./maps";

export function isApple(): boolean {
  const platform =
    (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform ??
    navigator.platform;
  return /mac|iphone|ipad|ipod/i.test(platform);
}

const MODIFIER_ORDER = ["Control", "Alt", "Shift", "Meta"];

/** The press a binding needs, written one way: modifiers sorted, `$mod` resolved, the key
 * lowercased. Optional modifiers (`[Shift]`) count as absent. */
export function normalizeBinding(binding: string, apple = isApple()): string {
  return binding
    .split(" ")
    .map((press) => {
      const parts = press.split("+");
      const key = parts.pop() ?? "";
      const modifiers = parts
        .filter((part) => !part.startsWith("["))
        .map((part) => (part === "$mod" ? (apple ? "Meta" : "Control") : part))
        .sort((a, b) => MODIFIER_ORDER.indexOf(a) - MODIFIER_ORDER.indexOf(b));
      return [...modifiers, key.toLowerCase()].join("+");
    })
    .join(" ");
}

/** Bindings that more than one shortcut of a map claims, for both platforms. */
export function duplicateBindings(map: readonly Shortcut[]): string[] {
  const duplicates = new Set<string>();
  for (const apple of [true, false]) {
    const seen = new Set<string>();
    for (const { keys } of map) {
      // Within one shortcut, two spellings of the same press are harmless.
      for (const key of new Set(keys.map((k) => normalizeBinding(k, apple)))) {
        if (seen.has(key)) duplicates.add(key);
        seen.add(key);
      }
    }
  }
  return [...duplicates].sort();
}

const KEY_LABELS: Record<string, string> = {
  arrowright: "→",
  arrowleft: "←",
  arrowup: "↑",
  arrowdown: "↓",
  enter: "Enter",
  escape: "Esc",
  space: "Space",
};

/** How a binding is printed on a `kbd`: "⌘1" on Apple systems, "Ctrl+1" elsewhere. */
export function bindingLabel(binding: string, apple = isApple()): string {
  return binding
    .split(" ")
    .map((press) => {
      const parts = press.split("+");
      const key = parts.pop() ?? "";
      const keyLabel = KEY_LABELS[key.toLowerCase()] ?? key.toUpperCase();
      // Optional modifiers are not printed: "[Shift]+?" is shown as "?".
      const modifiers = parts.filter((part) => !part.startsWith("["));
      const symbols = modifiers.map((part) => {
        const name = part === "$mod" ? (apple ? "Meta" : "Control") : part;
        if (apple) return { Meta: "⌘", Control: "⌃", Alt: "⌥", Shift: "⇧" }[name] ?? name;
        return { Meta: "Win", Control: "Ctrl", Alt: "Alt", Shift: "Shift" }[name] ?? name;
      });
      return apple ? [...symbols, keyLabel].join("") : [...symbols, keyLabel].join("+");
    })
    .join(" ");
}

/** The labels a shortcut shows: each key, or "first … last" for a range. */
export function shortcutLabels(shortcut: Shortcut, apple = isApple()): string[] {
  const labels = shortcut.keys.map((key) => bindingLabel(key, apple));
  if (shortcut.display === "range" && labels.length > 1) {
    return [labels[0] ?? "", labels[labels.length - 1] ?? ""];
  }
  return labels;
}

/** A binding in `aria-keyshortcuts` form ("Control+1", "ArrowRight", "I"). */
export function ariaBinding(binding: string, apple = isApple()): string {
  const parts = binding.split(" ")[0]?.split("+") ?? [];
  const key = parts.pop() ?? "";
  const modifiers = parts
    .filter((part) => !part.startsWith("["))
    .map((part) => (part === "$mod" ? (apple ? "Meta" : "Control") : part));
  return [...modifiers, key.length === 1 ? key.toUpperCase() : key].join("+");
}
