// The PDF reader (design 4.5): pages streamed from the backend with range requests, drawn
// only while near the screen, with a selectable text layer, zoom and `?page=` deep links.
import { useVirtualizer } from "@tanstack/react-virtual";
import { BookOpen, Minus, MoveHorizontal, Plus } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router";

import { useBackend } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAttachment } from "@/features/files/api";
import { openPdf, type PdfDocument, type PdfPageSize } from "@/lib/pdf";

const PAGE_GAP = 12;
const ZOOM_STEPS = [0.5, 0.67, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];
// Pages drawn beyond the visible ones, each way: enough to scroll without blanks, few enough
// that a 300-page document keeps only a handful of canvases in memory.
const OVERSCAN = 2;

type Zoom = { kind: "fit" } | { kind: "scale"; value: number };

export function ReaderPage() {
  const { t } = useTranslation();
  const { attachmentId } = useParams();
  if (!attachmentId) {
    return (
      <div className="grid h-full place-items-center p-6 text-center">
        <div className="max-w-sm space-y-2">
          <BookOpen aria-hidden className="mx-auto size-6 text-fg-muted" />
          <h1 className="text-h2">{t("reader.title")}</h1>
          <p className="text-ui text-fg-muted">{t("reader.nothingOpen")}</p>
        </div>
      </div>
    );
  }
  return <Reader key={attachmentId} attachmentId={attachmentId} />;
}

function usePdf(attachmentId: string) {
  const { connection } = useBackend();
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "ready"; document: PdfDocument; firstPage: PdfPageSize }
    | { status: "failed" }
  >({ status: "loading" });

  useEffect(() => {
    let document: PdfDocument | null = null;
    let stopped = false;
    const url = `${connection.baseUrl}/attachments/${encodeURIComponent(attachmentId)}/file`;
    const headers: Record<string, string> = connection.token
      ? { Authorization: `Bearer ${connection.token}` }
      : {};
    openPdf({ url, headers })
      .then(async (opened) => {
        document = opened;
        const firstPage = await opened.pageSize(1);
        if (!stopped) setState({ status: "ready", document: opened, firstPage });
      })
      .catch(() => {
        if (!stopped) setState({ status: "failed" });
      });
    return () => {
      stopped = true;
      void document?.destroy();
    };
  }, [attachmentId, connection]);

  return state;
}

function Reader({ attachmentId }: { attachmentId: string }) {
  const { t } = useTranslation();
  const attachment = useAttachment(attachmentId);
  const pdf = usePdf(attachmentId);
  const title = attachment.data?.file_name ?? t("reader.title");

  return (
    <div className="flex h-full min-h-0 flex-col">
      {pdf.status === "ready" ? (
        <PageList document={pdf.document} firstPage={pdf.firstPage} title={title} />
      ) : (
        <>
          <header className="border-b border-line px-4 py-2">
            <h1 className="truncate text-h3">{title}</h1>
          </header>
          <p
            role={pdf.status === "failed" ? "alert" : "status"}
            className={
              pdf.status === "failed" ? "p-6 text-ui text-danger" : "p-6 text-ui text-fg-muted"
            }
          >
            {pdf.status === "failed" ? t("reader.failed") : t("reader.loading")}
          </p>
        </>
      )}
    </div>
  );
}

function PageList({
  document,
  firstPage,
  title,
}: {
  document: PdfDocument;
  firstPage: PdfPageSize;
  title: string;
}) {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const scroller = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [zoom, setZoom] = useState<Zoom>({ kind: "fit" });
  const [current, setCurrent] = useState(1);
  const [pageInput, setPageInput] = useState("1");

  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const measure = () => {
      setWidth(element.clientWidth);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => {
      observer.disconnect();
    };
  }, []);

  // Fit width leaves a margin either side; papers are mostly one page size, so page 1 sets it.
  const fitScale = width > 0 ? Math.max(0.25, (width - 48) / firstPage.width) : 1;
  const scale = zoom.kind === "fit" ? fitScale : zoom.value;
  const pageHeight = Math.floor(firstPage.height * scale);
  const pageWidth = Math.floor(firstPage.width * scale);

  // eslint-disable-next-line react-hooks/incompatible-library -- only skips memoizing this component
  const virtualizer = useVirtualizer({
    count: document.numPages,
    getScrollElement: () => scroller.current,
    estimateSize: () => pageHeight + PAGE_GAP,
    overscan: OVERSCAN,
    paddingStart: PAGE_GAP,
  });

  // The size of every page changes with the zoom: measure again.
  useEffect(() => {
    virtualizer.measure();
  }, [virtualizer, pageHeight]);

  // A deep link (?page=12) opens at that page once the pages have their size.
  const requested = Number.parseInt(params.get("page") ?? "1", 10);
  const opened = useRef(false);
  useEffect(() => {
    if (opened.current || width === 0) return;
    opened.current = true;
    const page = Math.min(Math.max(Number.isNaN(requested) ? 1 : requested, 1), document.numPages);
    if (page > 1) virtualizer.scrollToIndex(page - 1, { align: "start" });
  }, [width, requested, document.numPages, virtualizer]);

  // The page indicator follows the scroll; the address keeps the page for a reload or link.
  const items = virtualizer.getVirtualItems();
  const offset = virtualizer.scrollOffset ?? 0;
  const visible = items.find(
    (item) => item.end > offset + (scroller.current?.clientHeight ?? 0) / 3,
  );
  const visibleIndex = visible?.index ?? 0;
  useEffect(() => {
    const page = visibleIndex + 1;
    setCurrent(page);
    setPageInput(String(page));
    if (!opened.current) return;
    const timer = setTimeout(() => {
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          next.set("page", String(page));
          return next;
        },
        { replace: true },
      );
    }, 300);
    return () => {
      clearTimeout(timer);
    };
  }, [visibleIndex, setParams]);

  function goTo(event: SyntheticEvent) {
    event.preventDefault();
    const page = Number.parseInt(pageInput, 10);
    if (Number.isNaN(page)) return;
    virtualizer.scrollToIndex(Math.min(Math.max(page, 1), document.numPages) - 1, {
      align: "start",
    });
  }

  function step(direction: 1 | -1) {
    const index = ZOOM_STEPS.findIndex((value) => value >= scale - 0.001);
    const from = index === -1 ? ZOOM_STEPS.length - 1 : index;
    const next = ZOOM_STEPS[Math.min(Math.max(from + direction, 0), ZOOM_STEPS.length - 1)];
    if (next !== undefined) setZoom({ kind: "scale", value: next });
  }

  const percent = useMemo(
    () => new Intl.NumberFormat(i18n.language, { style: "percent" }).format(scale),
    [i18n.language, scale],
  );

  return (
    <>
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-1.5">
        <h1 className="min-w-0 flex-1 truncate text-h3">{title}</h1>
        <form onSubmit={goTo} className="flex items-center gap-1 text-meta text-fg-muted">
          <Input
            aria-label={t("reader.page")}
            className="h-7 w-14 text-center"
            inputMode="numeric"
            value={pageInput}
            onChange={(event) => {
              setPageInput(event.target.value);
            }}
          />
          <span aria-live="polite">{t("reader.of", { total: document.numPages, current })}</span>
        </form>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("reader.zoomOut")}
            onClick={() => {
              step(-1);
            }}
          >
            <Minus />
          </Button>
          <span className="w-12 text-center text-meta tabular-nums">{percent}</span>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("reader.zoomIn")}
            onClick={() => {
              step(1);
            }}
          >
            <Plus />
          </Button>
          <Button
            variant={zoom.kind === "fit" ? "secondary" : "ghost"}
            size="icon"
            aria-label={t("reader.fitWidth")}
            aria-pressed={zoom.kind === "fit"}
            onClick={() => {
              setZoom({ kind: "fit" });
            }}
          >
            <MoveHorizontal />
          </Button>
        </div>
      </header>
      <div
        ref={scroller}
        role="document"
        aria-label={title}
        data-testid="reader-scroller"
        className="min-h-0 flex-1 overflow-auto bg-surface"
      >
        <div
          className="relative mx-auto"
          style={{ height: virtualizer.getTotalSize(), width: Math.max(pageWidth, 1) }}
        >
          {items.map((item) => (
            <div
              key={item.key}
              className="absolute top-0 left-0"
              style={{ transform: `translateY(${String(item.start)}px)` }}
            >
              <PageView
                document={document}
                pageNumber={item.index + 1}
                scale={scale}
                width={pageWidth}
                height={pageHeight}
              />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function PageView({
  document,
  pageNumber,
  scale,
  width,
  height,
}: {
  document: PdfDocument;
  pageNumber: number;
  scale: number;
  width: number;
  height: number;
}) {
  const { t } = useTranslation();
  const canvas = useRef<HTMLCanvasElement>(null);
  const textLayer = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!canvas.current || !textLayer.current) return;
    const rendered = document.renderPage(pageNumber, {
      canvas: canvas.current,
      textLayer: textLayer.current,
      scale,
    });
    rendered.done.catch(() => {
      setFailed(true);
    });
    return () => {
      rendered.dispose();
    };
  }, [document, pageNumber, scale]);

  return (
    <section
      aria-label={t("reader.pageLabel", { page: pageNumber })}
      data-page={pageNumber}
      className="relative overflow-hidden bg-raised shadow-popover"
      // A page is paper whatever the theme; pdf.js paints its own white background.
      style={{ width, height, colorScheme: "light" }}
    >
      <canvas ref={canvas} aria-hidden className="block" />
      <div ref={textLayer} className="textLayer" />
      {failed && (
        <p role="alert" className="absolute inset-0 grid place-items-center text-meta text-danger">
          {t("reader.pageFailed")}
        </p>
      )}
    </section>
  );
}
