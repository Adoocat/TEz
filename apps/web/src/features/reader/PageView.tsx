import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { PdfDocument, PdfPageSize } from "@/lib/pdf";

function pointIn(event: MouseEvent<HTMLElement>) {
  const box = event.currentTarget.getBoundingClientRect();
  return { x: event.clientX - box.left, y: event.clientY - box.top };
}

/** One drawn page: canvas, selectable text, and whatever lies on top (`children`). */
export function PageView({
  document,
  pageNumber,
  scale,
  width,
  height,
  onSize,
  onText,
  onPoint,
  onClick,
  children,
}: {
  document: PdfDocument;
  pageNumber: number;
  scale: number;
  width: number;
  height: number;
  /** The page's own size at scale 1; the list assumed page 1's until now. */
  onSize: (pageNumber: number, size: PdfPageSize) => void;
  /** The text layer is ready (null: gone again). */
  onText: (pageNumber: number, layer: HTMLElement | null) => void;
  /** The pointer over the page, in CSS pixels from its corner; null when it leaves. */
  onPoint?: (pageNumber: number, point: { x: number; y: number } | null) => void;
  onClick?: (pageNumber: number, point: { x: number; y: number }) => void;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const canvas = useRef<HTMLCanvasElement>(null);
  const textLayer = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  // The callbacks may be new on every render; drawing again because of that would be wasteful.
  const latest = useRef({ onSize, onText });
  useEffect(() => {
    latest.current = { onSize, onText };
  });

  useEffect(() => {
    let gone = false;
    document.pageSize(pageNumber).then(
      (size) => {
        if (!gone) latest.current.onSize(pageNumber, size);
      },
      () => {
        if (!gone) setFailed(true);
      },
    );
    return () => {
      gone = true;
    };
  }, [document, pageNumber]);

  useEffect(() => {
    const layer = textLayer.current;
    if (!canvas.current || !layer) return;
    const state = { gone: false };
    const rendered = document.renderPage(pageNumber, {
      canvas: canvas.current,
      textLayer: layer,
      scale,
    });
    rendered.done.then(
      () => {
        if (!state.gone) latest.current.onText(pageNumber, layer);
      },
      () => {
        if (!state.gone) setFailed(true);
      },
    );
    return () => {
      state.gone = true;
      latest.current.onText(pageNumber, null);
      rendered.dispose();
    };
  }, [document, pageNumber, scale]);

  return (
    <section
      aria-label={t("reader.pageLabel", { page: pageNumber })}
      data-page={pageNumber}
      className="relative mx-auto overflow-hidden bg-raised shadow-popover"
      // A page is paper whatever the theme; pdf.js paints its own white background.
      style={{ width, height, colorScheme: "light" }}
      onPointerMove={(event) => {
        onPoint?.(pageNumber, pointIn(event));
      }}
      onPointerLeave={() => {
        onPoint?.(pageNumber, null);
      }}
      onClick={(event) => {
        onClick?.(pageNumber, pointIn(event));
      }}
    >
      <canvas ref={canvas} aria-hidden className="block" />
      <div ref={textLayer} className="textLayer" />
      {children}
      {failed && (
        <p role="alert" className="absolute inset-0 grid place-items-center text-meta text-danger">
          {t("reader.pageFailed")}
        </p>
      )}
    </section>
  );
}
