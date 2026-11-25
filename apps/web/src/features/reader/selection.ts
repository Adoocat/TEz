// What the user selected in the text layer, as an anchor: boxes in PDF space, the quote, what
// stands around it, and which of the page's identical passages it is (ADR 0033).
import { fold } from "@/lib/text";
import { joinLines, toPdf } from "@/lib/pdfGeometry";
import type { PdfPageSize } from "@/lib/pdf";

import type { AnchorCreate } from "./api";
import { readLayer, spanOf } from "./layerText";

const CONTEXT = 120;

/** The text layer a selection starts in, and the selection cut to it (one page per anchor). */
export function selectionInLayer(
  selection: Selection | null,
  root: Element,
): { layer: HTMLElement; range: Range; page: number } | null {
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0).cloneRange();
  const startElement =
    range.startContainer instanceof Element
      ? range.startContainer
      : range.startContainer.parentElement;
  const layer = startElement?.closest<HTMLElement>(".textLayer");
  const page = Number(layer?.closest<HTMLElement>("[data-page]")?.dataset.page);
  if (!layer || !root.contains(layer) || Number.isNaN(page)) return null;
  // Dragging past the last line ends the selection in the next page, or outside the document.
  if (!layer.contains(range.endContainer)) range.setEnd(layer, layer.childNodes.length);
  return range.toString().trim() === "" ? null : { layer, range, page };
}

export function anchorOf(
  layer: HTMLElement,
  range: Range,
  page: number,
  size: PdfPageSize,
  scale: number,
): AnchorCreate | null {
  const read = readLayer(layer);
  const span = spanOf(read, range);
  if (!span) return null;
  const quote = read.text.slice(span.start, span.end).trim();
  if (quote === "") return null;
  const origin =
    layer.closest("[data-page]")?.getBoundingClientRect() ?? layer.getBoundingClientRect();
  const boxes = [...range.getClientRects()].map((rect) => ({
    left: rect.left - origin.left,
    top: rect.top - origin.top,
    width: rect.width,
    height: rect.height,
  }));
  const rects = joinLines(boxes).map((rect) => toPdf(size.transform, scale, rect));
  if (rects.length === 0) return null;
  return {
    kind: "text",
    page,
    rects,
    quote,
    prefix: read.text.slice(Math.max(0, span.start - CONTEXT), span.start),
    suffix: read.text.slice(span.end, span.end + CONTEXT),
    occurrence: before(read.text.slice(0, span.start), quote),
  };
}

/** How many times the passage stands before this one; letters and digits only, as the backend
 * compares them. */
function before(text: string, quote: string): number {
  const key = (value: string) => fold(value).replace(/[^\p{L}\p{N}]/gu, "");
  const [haystack, needle] = [key(text), key(quote)];
  if (needle === "") return 0;
  let count = 0;
  for (let at = haystack.indexOf(needle); at !== -1; at = haystack.indexOf(needle, at + 1)) {
    count += 1;
  }
  return count;
}
