// What lies on a page: its highlights and marked areas, and the rectangle being drawn.
import { useState, type PointerEvent } from "react";

import type { PdfPageSize } from "@/lib/pdf";
import { toPdf, toScreen, type PdfRect, type ScreenRect } from "@/lib/pdfGeometry";
import { cn } from "@/lib/cn";

import { highlightVar, type AnnotationView } from "./api";

const usable = (annotation: AnnotationView) =>
  annotation.anchor.status === "verified" || annotation.anchor.status === "unverified";

/** The annotation under a point of the page (CSS pixels), the smallest if several. */
export function annotationAt(
  annotations: readonly AnnotationView[],
  size: PdfPageSize,
  scale: number,
  point: { x: number; y: number },
): AnnotationView | null {
  let found: AnnotationView | null = null;
  let area = Infinity;
  for (const annotation of annotations) {
    if (!usable(annotation)) continue;
    for (const rect of annotation.anchor.rects) {
      const box = toScreen(size.transform, scale, rect as PdfRect);
      const inside =
        point.x >= box.left &&
        point.x <= box.left + box.width &&
        point.y >= box.top &&
        point.y <= box.top + box.height;
      if (inside && box.width * box.height < area) {
        found = annotation;
        area = box.width * box.height;
      }
    }
  }
  return found;
}

export function PageAnnotations({
  annotations,
  size,
  scale,
  selectedId,
}: {
  annotations: readonly AnnotationView[];
  size: PdfPageSize;
  scale: number;
  selectedId: string | null;
}) {
  // Nothing here takes the pointer: text under a highlight stays selectable.
  return annotations.filter(usable).flatMap((annotation) =>
    annotation.anchor.rects.map((rect, index) => (
      <div
        key={`${annotation.id}-${String(index)}`}
        aria-hidden
        data-testid="annotation"
        data-annotation={annotation.id}
        className={cn(
          "pointer-events-none absolute rounded-xs mix-blend-multiply",
          annotation.kind === "area" && "border-2 mix-blend-normal",
          annotation.id === selectedId && "ring-2 ring-primary",
        )}
        style={{
          ...toScreen(size.transform, scale, rect as PdfRect),
          ...(annotation.kind === "area"
            ? { borderColor: highlightVar(annotation.color) }
            : {
                backgroundColor: `color-mix(in srgb, ${highlightVar(annotation.color)} calc(var(--highlight-opacity) * 100%), transparent)`,
              }),
        }}
      />
    )),
  );
}

/** Over a page while the area tool is on: drag a rectangle. */
export function AreaTool({
  label,
  size,
  scale,
  onArea,
}: {
  label: string;
  size: PdfPageSize;
  scale: number;
  onArea: (rect: PdfRect) => void;
}) {
  const [from, setFrom] = useState<{ x: number; y: number } | null>(null);
  const [to, setTo] = useState<{ x: number; y: number } | null>(null);
  const pointOf = (event: PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.min(Math.max(event.clientX - box.left, 0), box.width),
      y: Math.min(Math.max(event.clientY - box.top, 0), box.height),
    };
  };
  const box: ScreenRect | null =
    from && to
      ? {
          left: Math.min(from.x, to.x),
          top: Math.min(from.y, to.y),
          width: Math.abs(to.x - from.x),
          height: Math.abs(to.y - from.y),
        }
      : null;
  return (
    <div
      role="img"
      aria-label={label}
      className="absolute inset-0 cursor-crosshair touch-none"
      onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        setFrom(pointOf(event));
        setTo(pointOf(event));
      }}
      onPointerMove={(event) => {
        if (from) setTo(pointOf(event));
      }}
      onPointerUp={() => {
        // A click is not an area.
        if (box && box.width > 8 && box.height > 8) onArea(toPdf(size.transform, scale, box));
        setFrom(null);
        setTo(null);
      }}
    >
      {box && (
        <div
          aria-hidden
          className="absolute border-2 border-dashed border-primary bg-primary-soft/40"
          style={box}
        />
      )}
    </div>
  );
}
