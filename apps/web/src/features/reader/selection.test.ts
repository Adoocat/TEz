import { beforeEach, describe, expect, it, vi } from "vitest";

import { anchorOf, selectionInLayer } from "./selection";

const SIZE = { width: 600, height: 800, transform: [1, 0, 0, -1, 0, 800] as const };

function page(number: number, ...lines: string[]) {
  const section = document.createElement("section");
  section.dataset.page = String(number);
  const layer = document.createElement("div");
  layer.className = "textLayer";
  for (const line of lines) {
    const span = document.createElement("span");
    span.textContent = line;
    layer.append(span, document.createElement("br"));
  }
  section.append(layer);
  document.body.append(section);
  return layer;
}

function select(from: [Node, number], to: [Node, number]) {
  const range = document.createRange();
  range.setStart(...from);
  range.setEnd(...to);
  const selection = getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
  return selection;
}

const text = (layer: HTMLElement, line: number) =>
  layer.querySelectorAll("span")[line]?.firstChild as Text;

beforeEach(() => {
  document.body.replaceChildren();
  // jsdom has no layout: one box per line of the selection.
  Range.prototype.getClientRects = () =>
    [new DOMRect(100, 50, 200, 12), new DOMRect(20, 64, 80, 12)] as unknown as DOMRectList;
});

describe("a selection as an anchor", () => {
  it("has the quote as read, its boxes in PDF space and what stands around it", () => {
    const layer = page(3, "We used a qualita-", "tive design with", "interviews.");
    const found = selectionInLayer(
      select([text(layer, 0), 8], [text(layer, 1), 11]),
      document.body,
    );
    if (!found) throw new Error("nothing selected");

    expect(anchorOf(found.layer, found.range, found.page, SIZE, 2)).toEqual({
      kind: "text",
      page: 3,
      rects: [
        [50, 769, 150, 775],
        [10, 762, 50, 768],
      ],
      quote: "a qualitative design",
      prefix: "We used ",
      suffix: " with interviews. ",
      occurrence: 0,
    });
  });

  it("says which of the same passages it is", () => {
    const layer = page(1, "the sample", "the Sample, the sample");
    const found = selectionInLayer(
      select([text(layer, 1), 12], [text(layer, 1), 22]),
      document.body,
    );
    if (!found) throw new Error("nothing selected");

    const anchor = anchorOf(found.layer, found.range, found.page, SIZE, 1);

    expect([anchor?.quote, anchor?.occurrence]).toEqual(["the sample", 2]);
  });

  it("stops at the end of the page it starts on", () => {
    const first = page(1, "ends here");
    const second = page(2, "goes on");
    const found = selectionInLayer(
      select([text(first, 0), 5], [text(second, 0), 4]),
      document.body,
    );

    expect(found?.page).toBe(1);
    expect(found?.range.toString()).toBe("here");
  });

  it("ignores selections outside a document, and empty ones", () => {
    const outside = document.createElement("p");
    outside.textContent = "menu text";
    document.body.append(outside);
    const node = outside.firstChild as Text;
    const layer = page(1, "some text");

    expect(selectionInLayer(select([node, 0], [node, 4]), document.body)).toBeNull();
    expect(
      selectionInLayer(select([text(layer, 0), 2], [text(layer, 0), 2]), document.body),
    ).toBeNull();
    expect(
      selectionInLayer(
        select([text(layer, 0), 0], [text(layer, 0), 4]),
        document.createElement("div"),
      ),
    ).toBeNull();
    vi.restoreAllMocks();
  });
});
