// Marks the matches of the reader's search in pdf.js's text layer, with the CSS Custom Highlight
// API: the layer's DOM, which selections and anchors depend on, is not touched. A webview
// without the API still jumps to the page; it only draws no marks.
import { foldWithMap } from "@/lib/text";

import { readLayer } from "./layerText";

const FIND = "tez-find";
const CURRENT = "tez-find-current";

/** Where `query` is in a text layer. Case, accents, line ends and line-end hyphens do not
 * matter, as in the backend's search. */
export function findRanges(layer: Element, query: string): Range[] {
  const needle = foldWithMap(query).folded.split(/\s+/).filter(Boolean).join(" ");
  if (needle === "") return [];
  const { text, places } = readLayer(layer);
  const { folded, origin } = foldWithMap(text);
  const ranges: Range[] = [];
  for (
    let at = folded.indexOf(needle);
    at !== -1;
    at = folded.indexOf(needle, at + needle.length)
  ) {
    const start = places[origin[at] ?? -1];
    const end = places[origin[at + needle.length - 1] ?? -1];
    if (!start || !end) continue;
    const range = layer.ownerDocument.createRange();
    range.setStart(start.node, start.offset);
    range.setEnd(end.node, Math.min(end.offset + 1, end.node.length));
    ranges.push(range);
  }
  return ranges;
}

function registry() {
  return typeof CSS !== "undefined" && "highlights" in CSS ? CSS.highlights : null;
}

export function drawFind(pages: Iterable<Range[]>, current: Range | null): void {
  const highlights = registry();
  if (!highlights) return;
  const others = [...pages].flat().filter((range) => range !== current);
  highlights.set(FIND, new Highlight(...others));
  const marked = new Highlight(...(current ? [current] : []));
  marked.priority = 1;
  highlights.set(CURRENT, marked);
}

export function clearFind(): void {
  const highlights = registry();
  highlights?.delete(FIND);
  highlights?.delete(CURRENT);
}
