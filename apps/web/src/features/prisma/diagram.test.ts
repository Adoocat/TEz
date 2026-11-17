// Task 35: the PRISMA 2020 diagram is a standalone SVG whose every number is Task 34's.
import { describe, expect, it } from "vitest";

import { sampleCounts } from "@/test/prismaFixtures";

import { boxKeys, prismaSvg, printPalette, type BoxKey, type DiagramText } from "./diagram";

function text(labels: Partial<Record<BoxKey, string>> = {}): DiagramText {
  return {
    title: (key) => labels[key] ?? `[${key}]`,
    n: (value) => `(n = ${String(value)})`,
    line: (label, value) => `${label} (n = ${String(value)})`,
    source: (name) => name || "unlogged",
    method: (method, round) => (round === null ? method : `${method} ${String(round)}`),
    reason: (code, reason) => (code ? `${code}: ${reason ?? ""}` : "no reason"),
    awaiting: "Awaiting decision",
    duplicates: "Duplicates",
    notTaken: "Removed for other reasons",
    documentTitle: "PRISMA 2020 flow diagram",
  };
}

function parse(svg: string): Document {
  return new DOMParser().parseFromString(svg, "image/svg+xml");
}

/** The drawn text, with wrapped lines joined back together. */
function drawn(svg: string): string {
  return parse(svg).documentElement.textContent.replace(/\s+/g, " ");
}

describe("the PRISMA diagram", () => {
  it("is a valid SVG document that opens on its own", () => {
    const svg = prismaSvg(sampleCounts, text(), printPalette);
    const document = parse(svg);

    expect(document.getElementsByTagName("parsererror")).toHaveLength(0);
    expect(document.documentElement.tagName).toBe("svg");
    expect(document.documentElement.getAttribute("xmlns")).toBe("http://www.w3.org/2000/svg");
    expect(document.documentElement.getAttribute("viewBox")).toMatch(/^0 0 \d+ \d+$/);
    // Nothing from outside the file: no stylesheet, no CSS variables, no linked fonts.
    expect(svg).not.toMatch(/var\(--|@import|<link|href="http/);
  });

  it("shows every number of Task 34's counts", () => {
    const shown = drawn(prismaSvg(sampleCounts, text(), printPalette));
    const numbers = [
      // Databases: identified, per source, duplicates, screened, excluded, sought,
      // not retrieved, assessed, reports excluded per reason, waiting.
      1425, 842, 583, 294, 1131, 1000, 31, 100, 7, 90, 72, 50, 22, 3,
      // Other methods.
      45, 40, 6, 39, 30, 9, 1, 8, 3,
      // Included, both branches.
      23,
    ];
    for (const n of numbers) expect(shown).toContain(`(n = ${String(n)})`);
    expect(shown).toContain("Scopus (n = 842)");
    expect(shown).toContain("pubmed (n = 583)");
    expect(shown).toContain("citation_backward 1 (n = 40)");
    expect(shown).toContain("thesis (n = 5)");
    expect(shown).toContain("[included] (n = 23)");
  });

  it("uses the saved titles and escapes them", () => {
    const shown = drawn(
      prismaSvg(sampleCounts, text({ db_identified: "Kayıtlar <veri> & tabanlar" }), printPalette),
    );

    expect(shown).toContain("Kayıtlar <veri> & tabanlar (n = 1425)");
    expect(shown).toContain("E2: No <empirical> data & no code (n = 22)");
  });

  it("titles every box from the list the editor offers", () => {
    const shown = drawn(prismaSvg(sampleCounts, text(), printPalette));
    for (const key of boxKeys) expect(shown).toContain(`[${key}]`);
  });

  it("prints in black and white", () => {
    const svg = prismaSvg(sampleCounts, text(), printPalette);
    const colours = new Set(svg.match(/#[0-9a-fA-F]{6}\b/g));

    for (const colour of colours) {
      const [r, g, b] = [1, 3, 5].map((i) => colour.slice(i, i + 2));
      expect(r === g && g === b, colour).toBe(true);
    }
  });
});
