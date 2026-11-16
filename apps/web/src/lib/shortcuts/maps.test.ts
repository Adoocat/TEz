// Task 30 acceptance: a key bound twice in one context fails here.
import { describe, expect, it } from "vitest";

import en from "../../../locales/en/common.json";
import tr from "../../../locales/tr/common.json";

import { ariaBinding, bindingLabel, duplicateBindings, shortcutLabels } from "./keys";
import { shortcutContexts, shortcutMaps, type Shortcut } from "./maps";

describe("the shortcut maps", () => {
  it.each(shortcutContexts)("bind each key once in the %s context", (context) => {
    expect(duplicateBindings(shortcutMaps[context])).toEqual([]);
  });

  it.each(shortcutContexts)("name each shortcut once in the %s context", (context) => {
    const ids = (shortcutMaps[context] as readonly Shortcut[]).map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it.each(shortcutContexts)("label every %s shortcut in Turkish and English", (context) => {
    for (const { id } of shortcutMaps[context] as readonly Shortcut[]) {
      for (const locale of [tr, en]) {
        const actions = locale.shortcuts.actions as Record<string, Record<string, string>>;
        expect(actions[context]?.[id], `${context}.${id}`).toBeTruthy();
      }
    }
  });

  it("may reuse a key in another context", () => {
    expect(duplicateBindings([...shortcutMaps.screening, ...shortcutMaps.reader])).toContain("j");
  });
});

describe("duplicate detection", () => {
  it.each([
    ["a letter in either case", ["i"], ["I"], "i"],
    ["$mod and the platform's own modifier", ["$mod+1"], ["Control+1"], "Control+1"],
    ["$mod on Apple systems", ["$mod+k"], ["Meta+K"], "Meta+k"],
    ["modifiers in another order", ["Shift+Alt+d"], ["Alt+Shift+D"], "Alt+Shift+d"],
    ["an optional modifier", ["[Shift]+?"], ["?"], "?"],
  ])("catches %s", (_, first, second, expected) => {
    const map = [
      { id: "one", keys: first },
      { id: "two", keys: second },
    ];
    expect(duplicateBindings(map)).toEqual([expected]);
  });

  it("lets one shortcut list the same press twice", () => {
    expect(duplicateBindings([{ id: "one", keys: ["e", "E"] }])).toEqual([]);
  });
});

describe("labels", () => {
  it.each([
    ["$mod+1", true, "⌘1"],
    ["$mod+1", false, "Ctrl+1"],
    ["$mod+Shift+k", true, "⌘⇧K"],
    ["[Shift]+?", false, "?"],
    ["ArrowRight", false, "→"],
    ["i", false, "I"],
    ["Space", false, "Space"],
  ])("print %s (Apple: %s) as %s", (binding, apple, label) => {
    expect(bindingLabel(binding, apple)).toBe(label);
  });

  it("print a range as its ends", () => {
    expect(shortcutLabels(shortcutMaps.global[1], false)).toEqual(["Ctrl+1", "Ctrl+7"]);
    expect(shortcutLabels(shortcutMaps.screening[2], false)).toEqual(["1", "9"]);
  });

  it("give buttons an aria-keyshortcuts value", () => {
    expect(ariaBinding("$mod+1", false)).toBe("Control+1");
    expect(ariaBinding("i", false)).toBe("I");
    expect(ariaBinding("ArrowRight", false)).toBe("ArrowRight");
  });
});
