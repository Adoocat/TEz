import { describe, expect, it } from "vitest";

import { findRanges } from "./findHighlights";

/** A text layer as pdf.js writes it: a span per run, a <br> at each line's end. */
function layer(...lines: string[][]): HTMLElement {
  const root = document.createElement("div");
  for (const runs of lines) {
    for (const run of runs) {
      const span = document.createElement("span");
      span.textContent = run;
      root.append(span);
    }
    root.append(document.createElement("br"));
  }
  document.body.replaceChildren(root);
  return root;
}

function found(root: HTMLElement, query: string) {
  return findRanges(root, query).map((range) => range.toString());
}

describe("findRanges", () => {
  it("ignores case and accents, also Turkish ones", () => {
    const root = layer(["Işık ve ", "IŞIK"], ["isik"]);

    expect(found(root, "ışık")).toEqual(["Işık", "IŞIK", "isik"]);
  });

  it("finds a phrase over runs and lines", () => {
    const root = layer(["grounded", " ", "the"], ["ory of text"]);

    expect(found(layer(["we used grounded"], ["theory here"]), "grounded theory")).toEqual([
      "groundedtheory",
    ]);
    expect(found(root, "grounded the")).toEqual(["grounded the"]);
  });

  it("joins a word broken at the end of a line", () => {
    expect(found(layer(["an inter-"], ["disciplinary team"]), "interdisciplinary")).toEqual([
      "inter-disciplinary",
    ]);
  });

  it("finds ligatures and nothing for an empty query", () => {
    const root = layer(["e\ufb03cient o\ufb03ce"]);

    expect(found(root, "efficient")).toEqual(["e\ufb03cient"]);
    expect(found(root, "  ")).toEqual([]);
  });
});
