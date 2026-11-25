import type { PdfPageSize } from "@/lib/pdf";
import { toScreen, type PdfRect } from "@/lib/pdfGeometry";

import type { AnchorView } from "./api";

/** A place on the page, shown for a moment after a jump to it. */
export function AnchorFlash({
  anchor,
  size,
  scale,
}: {
  anchor: AnchorView;
  size: PdfPageSize;
  scale: number;
}) {
  return anchor.rects.map((rect, index) => (
    <div
      // The boxes of an anchor never change order.
      key={index}
      aria-hidden
      data-testid="anchor-flash"
      className="pointer-events-none absolute animate-pulse rounded-xs bg-[color-mix(in_srgb,var(--color-highlight-yellow)_45%,transparent)] ring-2 ring-primary motion-reduce:animate-none"
      style={toScreen(size.transform, scale, rect as PdfRect)}
    />
  ));
}
