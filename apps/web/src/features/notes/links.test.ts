import { describe, expect, it } from "vitest";

import { linksIn, nameLinks, writeLink } from "./links";
import { possibleParents, treeOf } from "./tree";
import { noteView } from "@/test/fakeBackend";

describe("links in a note", () => {
  it("reads both ways of writing one", () => {
    const text = "See [Kim 2024](tez:paper/p1), [[Işık]] and [web](https://example.org).";

    expect(linksIn(text).map((l) => [l.label, l.type, l.id, text.slice(l.from, l.to)])).toEqual([
      ["Kim 2024", "paper", "p1", "[Kim 2024](tez:paper/p1)"],
      ["Işık", null, null, "[[Işık]]"],
    ]);
  });

  it("writes links that read back, whatever the title", () => {
    const written = writeLink("A [bracketed]\n title", "note", "n-1");

    expect(written).toBe("[A (bracketed) title](tez:note/n-1)");
    expect(linksIn(written)).toHaveLength(1);
  });

  it("turns names into Markdown links for the preview", () => {
    expect(nameLinks("[[ Işık hızı ]]")).toBe(
      "[Işık hızı](tez:name/I%C5%9F%C4%B1k%20h%C4%B1z%C4%B1)",
    );
  });
});

describe("the note tree", () => {
  const notes = [
    noteView({ id: "b", title: "10 Sonuç" }),
    noteView({ id: "a", title: "2 Yöntem" }),
    noteView({ id: "c", title: "Örneklem", parent_id: "a" }),
    noteView({ id: "d", title: "Lost child", parent_id: "gone" }),
  ];

  it("sorts siblings by title, numbers by value, and keeps orphans", () => {
    expect(treeOf(notes, "tr").map(({ note, depth }) => [note.id, depth])).toEqual([
      ["a", 0],
      ["c", 1],
      ["b", 0],
      ["d", 0],
    ]);
  });

  it("offers no place inside the note itself", () => {
    expect(possibleParents(notes, "a").map((n) => n.id)).toEqual(["b", "d"]);
  });
});
