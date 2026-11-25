import type { PdfPageSize } from "@/lib/pdf";
import { toScreen, type PdfRect } from "@/lib/pdfGeometry";

import type { AnnotationView } from "./api";

/** The comment of the highlight under the pointer. */
export function HoverNote({
  annotation,
  size,
  scale,
}: {
  annotation: AnnotationView;
  size: PdfPageSize;
  scale: number;
}) {
  const rect = annotation.anchor.rects.at(-1);
  if (!rect) return null;
  const box = toScreen(size.transform, scale, rect as PdfRect);
  return (
    <p
      role="tooltip"
      className="pointer-events-none absolute z-[var(--z-popover)] max-w-72 rounded-md border border-line bg-raised px-2 py-1 text-ui whitespace-pre-wrap text-fg shadow-popover"
      style={{ left: box.left, top: box.top + box.height + 4 }}
    >
      {annotation.comment}
    </p>
  );
}
