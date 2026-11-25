// Marks the matches of the reader's search in pdf.js's text layer, with the CSS Custom Highlight
// API: the layer's DOM, which selections and anchors depend on, is not touched. A webview
// without the API still jumps to the page; it only draws no marks.
import { foldWithMap } from "@/lib/text";

const FIND = "tez-find";
const CURRENT = "tez-find-current";

interface Place {
  node: Text;
  offset: number;
}

/** Where `query` is in a text layer. Case, accents, line ends and line-end hyphens do not
 * matter, as in the backend's search. */
export function findRanges(layer: Element, query: string): Range[] {
  const needle = foldWithMap(query).folded.split(/\s+/).filter(Boolean).join(" ");
  if (needle === "") return [];
  let text = "";
  const places: Place[] = [];
  const addSpace = (place: Place | undefined) => {
    if (place && !text.endsWith(" ")) {
      text += " ";
      places.push(place);
    }
  };
  const walker = layer.ownerDocument.createTreeWalker(
    layer,
    NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
  );
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node instanceof Element) {
      // pdf.js puts a <br> at the end of each line.
      if (node.tagName !== "BR") continue;
      if (/[\p{L}][-­‐]$/u.test(text)) {
        text = text.slice(0, -1);
        places.pop();
      } else {
        addSpace(places.at(-1));
      }
      continue;
    }
    const { folded, origin } = foldWithMap((node as Text).data);
    for (let i = 0; i < folded.length; i += 1) {
      const char = folded[i] ?? "";
      const place = { node: node as Text, offset: origin[i] ?? 0 };
      if (/\s/.test(char)) addSpace(place);
      else {
        text += char;
        places.push(place);
      }
    }
  }
  const ranges: Range[] = [];
  for (let at = text.indexOf(needle); at !== -1; at = text.indexOf(needle, at + needle.length)) {
    const start = places[at];
    const end = places[at + needle.length - 1];
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
