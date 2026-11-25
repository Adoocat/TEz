import { describe, expect, it } from "vitest";

import { createI18n } from "@/i18n";
import { linksIn } from "@/features/notes/links";
import { anchorView } from "@/test/fakeBackend";

import { quoteBlock, quoteWithSource, sourceOf } from "./quote";

const t = createI18n("en").t;
const tr = createI18n("tr").t;

describe("a quoted passage", () => {
  it("names its source in the user's language", () => {
    const anchor = anchorView({ page: 7 });

    expect(sourceOf(anchor, t)).toBe("Lovelace et al. 2024, p. 7");
    expect(sourceOf(anchor, tr)).toBe("Lovelace vd. 2024, s. 7");
    expect(
      sourceOf(anchorView({ paper: { ...anchor.paper, author_count: 1, year: null } }), t),
    ).toBe("Lovelace, p. 1");
    expect(sourceOf(anchorView({ paper: { ...anchor.paper, first_author: null } }), t)).toBe(
      "First paper 2024, p. 1",
    );
  });

  it("becomes a block quote with a chip that reads back as a link to the place", () => {
    const block = quoteBlock(anchorView({ id: "a7", page: 7, quote: "the *best* [1] of_all" }), t);

    expect(block).toBe(
      "> the \\*best\\* \\[1\\] of\\_all\n>\n> [Lovelace et al. 2024, p. 7](tez:anchor/a7)",
    );
    expect(linksIn(block).map((l) => [l.type, l.id])).toEqual([["anchor", "a7"]]);
  });

  it("is only the chip for a marked area", () => {
    expect(quoteBlock(anchorView({ id: "a9", kind: "area", quote: "" }), t)).toBe(
      "[Lovelace et al. 2024, p. 1](tez:anchor/a9)",
    );
  });

  it("goes to the clipboard with its source", () => {
    expect(quoteWithSource(anchorView(), t)).toBe(
      "\u201cforty-two participants\u201d (Lovelace et al. 2024, p. 1)",
    );
  });
});
