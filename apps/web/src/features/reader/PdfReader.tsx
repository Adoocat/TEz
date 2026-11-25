// A PDF with its toolbar (design 4.5): pages streamed from the backend with range requests,
// drawn only while near the screen, with selectable text, zoom, search and `?page=` links.
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  Check,
  Copy,
  MapPinOff,
  Maximize,
  Minimize,
  Minus,
  MoveHorizontal,
  NotebookPen,
  PanelLeft,
  Plus,
  ScanText,
  Search,
  SquareDashed,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { useBackend } from "@/app/backend";
import { useLayoutStore } from "@/app/layout/uiStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAttachment } from "@/features/files/api";
import { ApiError } from "@/lib/api/query";
import { openPdf, type PdfDocument, type PdfPageSize } from "@/lib/pdf";
import { toScreen, type PdfRect } from "@/lib/pdfGeometry";
import { useShortcuts } from "@/lib/shortcuts/useShortcuts";
import { ariaShortcut } from "@/lib/shortcuts/ShortcutKeys";

import { AnchorFlash } from "./AnchorFlash";
import { annotationAt, AreaTool, PageAnnotations } from "./Annotations";
import {
  useAnnotations,
  useCreateAnchor,
  useCreateAnnotation,
  type AnchorView,
  type AnnotationView,
  type HighlightColor,
} from "./api";
import { DocumentPanel } from "./DocumentPanel";
import { FindBar } from "./FindBar";
import { HoverNote } from "./HoverNote";
import { PageView } from "./PageView";
import { quoteWithSource } from "./quote";
import { QuoteToNote, type QuotedIn } from "./QuoteToNote";
import { anchorOf, selectionInLayer } from "./selection";
import { SelectionToolbar } from "./SelectionToolbar";
import { useReaderPanel, useReaderSelection, useReaderTabs, useReadingPanel } from "./store";
import { useAnchorTarget } from "./useAnchorTarget";
import { useFindInDocument } from "./useFindInDocument";
import { useTextSelection } from "./useTextSelection";

const PAGE_GAP = 12;
const NOTICE_MS = 6000;
const ZOOM_STEPS = [0.5, 0.67, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];
// Pages drawn beyond the visible ones, each way: enough to scroll without blanks, few enough
// that a 300-page document keeps only a handful of canvases in memory.
const OVERSCAN = 2;

type Zoom = { kind: "fit" } | { kind: "scale"; value: number };

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

/** `embedded` (full-text screening, Task 33) leaves the address, the letter keys and the
 * document panel alone: the screen around it owns them. */
export function PdfReader({
  attachmentId,
  embedded = false,
}: {
  attachmentId: string;
  embedded?: boolean;
}) {
  const { t } = useTranslation();
  const attachment = useAttachment(attachmentId);
  const pdf = usePdf(attachmentId);
  const title = attachment.data?.file_name ?? t("reader.title");
  const Heading = embedded ? "h2" : "h1";

  return (
    <div className="flex h-full min-h-0 flex-col">
      {pdf.status === "ready" ? (
        <OpenDocument
          attachmentId={attachmentId}
          document={pdf.document}
          firstPage={pdf.firstPage}
          title={title}
          scanned={attachment.data?.text_status === "needs_ocr"}
          embedded={embedded}
        />
      ) : (
        <>
          <header className="border-b border-line px-4 py-2">
            <Heading className="truncate text-h3">{title}</Heading>
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

function OpenDocument({
  attachmentId,
  document,
  firstPage,
  title,
  scanned,
  embedded,
}: {
  attachmentId: string;
  document: PdfDocument;
  firstPage: PdfPageSize;
  title: string;
  scanned: boolean;
  embedded: boolean;
}) {
  // Embedded, the file name is a section heading under the screen's own title.
  const Heading = embedded ? "h2" : "h1";
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const panel = useReaderPanel();
  const { focus, setFocus } = useLayoutStore();
  const rememberPage = useReaderTabs((state) => state.setPage);
  const scroller = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [zoom, setZoom] = useState<Zoom>({ kind: "fit" });
  const [current, setCurrent] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  // Pages drawn so far; the rest are assumed to be like page 1.
  const [sizes, setSizes] = useState<ReadonlyMap<number, PdfPageSize>>(new Map());

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
  const boxOf = (page: number) => {
    const size = sizes.get(page) ?? firstPage;
    return { width: Math.floor(size.width * scale), height: Math.floor(size.height * scale) };
  };
  const widest = Math.max(
    Math.floor(firstPage.width * scale),
    ...[...sizes.keys()].map((page) => boxOf(page).width),
  );

  // eslint-disable-next-line react-hooks/incompatible-library -- only skips memoizing this component
  const virtualizer = useVirtualizer({
    count: document.numPages,
    getScrollElement: () => scroller.current,
    estimateSize: (index) => boxOf(index + 1).height + PAGE_GAP,
    overscan: OVERSCAN,
    paddingStart: PAGE_GAP,
  });

  // The size of every page changes with the zoom: measure again.
  useEffect(() => {
    virtualizer.measure();
  }, [virtualizer, scale, firstPage]);

  const onSize = useCallback(
    (page: number, size: PdfPageSize) => {
      setSizes((known) => (known.has(page) ? known : new Map(known).set(page, size)));
      if (size.height === firstPage.height) return;
      // Keeps what is being read in place when a page above turns out taller or shorter.
      virtualizer.resizeItem(page - 1, Math.floor(size.height * scale) + PAGE_GAP);
    },
    [firstPage, scale, virtualizer],
  );

  const goToPage = useCallback(
    (page: number) => {
      virtualizer.scrollToIndex(Math.min(Math.max(page, 1), document.numPages) - 1, {
        align: "start",
      });
    },
    [virtualizer, document.numPages],
  );

  // A deep link (?page=12) opens at that page once the pages have their size.
  const requested = Number.parseInt((embedded ? null : params.get("page")) ?? "1", 10);
  const firstShown = Number.isNaN(requested) ? 1 : requested;
  const opened = useRef(false);
  useEffect(() => {
    if (opened.current || width === 0) return;
    opened.current = true;
    if (firstShown > 1) goToPage(firstShown);
  }, [width, firstShown, goToPage]);

  const find = useFindInDocument({
    attachmentId,
    initialQuery: embedded ? "" : (params.get("find") ?? ""),
    initialPage: firstShown,
    goToPage,
  });

  const goToAnchor = useCallback(
    (anchor: AnchorView) => {
      void document.pageSize(anchor.page).then((size) => {
        const [first] = anchor.rects;
        const top = first ? toScreen(size.transform, scale, first as PdfRect).top : 0;
        const start = virtualizer.getOffsetForIndex(anchor.page - 1, "start")?.[0] ?? 0;
        // A third from the top: the passage with what leads to it.
        const above = (scroller.current?.clientHeight ?? 0) / 3;
        virtualizer.scrollToOffset(Math.max(0, start + top - above));
      });
    },
    [document, scale, virtualizer],
  );
  const target = useAnchorTarget({ enabled: !embedded, ready: width > 0, goTo: goToAnchor });

  // --- highlights ---
  const annotations = useAnnotations(attachmentId);
  const byPage = useMemo(() => {
    const pages = new Map<number, AnnotationView[]>();
    for (const annotation of annotations.data ?? []) {
      const { page } = annotation.anchor;
      pages.set(page, [...(pages.get(page) ?? []), annotation]);
    }
    return pages;
  }, [annotations.data]);
  const create = useCreateAnnotation(attachmentId);
  const createAnchor = useCreateAnchor(attachmentId);
  // The passage waiting for a note to go to.
  const [quoting, setQuoting] = useState<AnchorView | null>(null);
  const [notice, setNotice] = useState<
    { kind: "copied" } | { kind: "quoted"; note: QuotedIn } | null
  >(null);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => {
      setNotice(null);
    }, NOTICE_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [notice]);
  const setReadingTab = useReadingPanel((state) => state.setTab);
  const { selection, clear: clearSelection } = useTextSelection(scroller);
  const { selectedId, color, select, setColor } = useReaderSelection();
  const [areaTool, setAreaTool] = useState(false);
  const [hovered, setHovered] = useState<AnnotationView | null>(null);
  const openPanel = useLayoutStore((state) => state.openInspector);

  /** The selection as an anchor; null when there is none. */
  async function selectedAnchor() {
    // What is selected now: the toolbar's copy can be a moment old.
    const found = scroller.current && selectionInLayer(getSelection(), scroller.current);
    if (!found) return null;
    const { layer, range, page } = found;
    return anchorOf(layer, range, page, await document.pageSize(page), scale);
  }

  async function highlight(chosen: HighlightColor, { comment = false } = {}) {
    const anchor = await selectedAnchor();
    if (!anchor) return;
    setColor(chosen);
    const made = await create.mutateAsync({ anchor, color: chosen, comment: "" });
    clearSelection();
    select(made.id, { edit: comment });
    if (comment && !embedded) openPanel();
  }

  /** Remember the selected place, then do something with it. */
  async function withAnchor(onAnchor: (anchor: AnchorView) => void) {
    const selected = await selectedAnchor();
    if (!selected) return;
    const anchor = await createAnchor.mutateAsync(selected);
    clearSelection();
    onAnchor(anchor);
  }

  async function copyWithSource() {
    await withAnchor((anchor) => {
      void navigator.clipboard.writeText(quoteWithSource(anchor, t)).then(() => {
        setNotice({ kind: "copied" });
      });
    });
  }

  async function markArea(page: number, rect: PdfRect) {
    setAreaTool(false);
    const made = await create.mutateAsync({
      anchor: { kind: "area", page, rects: [rect], quote: "", prefix: "", suffix: "" },
      color,
      comment: "",
    });
    select(made.id);
  }

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
    if (!opened.current || embedded) return;
    const timer = setTimeout(() => {
      rememberPage(attachmentId, page);
      setParams(
        (previous) => {
          const next = new URLSearchParams(previous);
          next.set("page", String(page));
          // These were asked for once; going back to this address should not repeat them.
          next.delete("find");
          next.delete("anchor");
          return next;
        },
        { replace: true },
      );
    }, 300);
    return () => {
      clearTimeout(timer);
    };
  }, [visibleIndex, setParams, embedded, attachmentId, rememberPage]);

  function goTo(event: SyntheticEvent) {
    event.preventDefault();
    const page = Number.parseInt(pageInput, 10);
    if (!Number.isNaN(page)) goToPage(page);
  }

  function step(direction: 1 | -1) {
    const index = ZOOM_STEPS.findIndex((value) => value >= scale - 0.001);
    const from = index === -1 ? ZOOM_STEPS.length - 1 : index;
    const next = ZOOM_STEPS[Math.min(Math.max(from + direction, 0), ZOOM_STEPS.length - 1)];
    if (next !== undefined) setZoom({ kind: "scale", value: next });
  }

  // J / K turn the page (design-prompt §6, reader context).
  useShortcuts(
    "reader",
    {
      nextPage: () => {
        goToPage(current + 1);
      },
      previousPage: () => {
        goToPage(current - 1);
      },
      focusMode: () => {
        setFocus(!focus);
      },
      highlight: () => {
        void highlight(color);
      },
      quote: () => {
        if (selection) void withAnchor(setQuoting);
        else {
          // Nothing selected: the notes about this paper.
          setReadingTab("notes");
          openPanel();
        }
      },
    },
    { enabled: !embedded },
  );
  useShortcuts("reader", {
    find: () => {
      find.show(current);
    },
  });

  // Escape leaves focus mode; leaving the reader does too.
  useEffect(() => {
    if (!focus || embedded) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) setFocus(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [focus, setFocus, embedded]);

  const percent = useMemo(
    () => new Intl.NumberFormat(i18n.language, { style: "percent" }).format(scale),
    [i18n.language, scale],
  );
  const failure = create.error ?? createAnchor.error;
  const showPanel = panel.open && !embedded && !focus;

  return (
    <>
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-1.5">
        {!embedded && !focus && (
          <Button
            variant={panel.open ? "secondary" : "ghost"}
            size="icon"
            aria-label={t("reader.togglePanel")}
            aria-pressed={panel.open}
            onClick={panel.toggle}
          >
            <PanelLeft />
          </Button>
        )}
        <Heading className="min-w-0 flex-1 truncate text-h3">{title}</Heading>
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
          <Button
            variant={find.open ? "secondary" : "ghost"}
            size="icon"
            aria-label={t("reader.find.open")}
            aria-keyshortcuts={ariaShortcut("reader", "find")}
            aria-expanded={find.open}
            onClick={() => {
              if (find.open) find.close();
              else find.show(current);
            }}
          >
            <Search />
          </Button>
          <Button
            variant={areaTool ? "secondary" : "ghost"}
            size="icon"
            aria-label={t("reader.areaTool")}
            title={t("reader.areaToolHint")}
            aria-pressed={areaTool}
            onClick={() => {
              setAreaTool(!areaTool);
            }}
          >
            <SquareDashed />
          </Button>
          {!embedded && (
            <Button
              variant={focus ? "secondary" : "ghost"}
              size="icon"
              aria-label={t("reader.focus")}
              title={t("reader.focusHint")}
              aria-keyshortcuts={ariaShortcut("reader", "focusMode")}
              aria-pressed={focus}
              onClick={() => {
                setFocus(!focus);
              }}
            >
              {focus ? <Minimize /> : <Maximize />}
            </Button>
          )}
        </div>
      </header>
      {find.open && (
        <FindBar
          query={find.query}
          results={find.results}
          position={find.position}
          onQuery={(query) => {
            find.setQuery(query, current);
          }}
          onStep={find.step}
          onClose={find.close}
        />
      )}
      {scanned && (
        <p
          role="note"
          className="flex items-center gap-2 border-b border-line bg-surface px-4 py-1.5 text-meta text-fg-muted"
        >
          <ScanText aria-hidden className="size-4 shrink-0" />
          {t("reader.noText")}
        </p>
      )}
      {selection && !areaTool && (
        <SelectionToolbar
          at={selection.at}
          color={color}
          onHighlight={(chosen) => {
            void highlight(chosen);
          }}
          onComment={() => {
            void highlight(color, { comment: true });
          }}
        >
          <Button
            size="sm"
            variant="ghost"
            aria-keyshortcuts={ariaShortcut("reader", "quote")}
            onClick={() => void withAnchor(setQuoting)}
          >
            <NotebookPen aria-hidden />
            {t("reader.quote.action")}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => void copyWithSource()}>
            <Copy aria-hidden />
            {t("reader.quote.copy")}
          </Button>
        </SelectionToolbar>
      )}
      {quoting && (
        <QuoteToNote
          anchor={quoting}
          onDone={(note) => {
            setQuoting(null);
            setNotice({ kind: "quoted", note });
          }}
          onCancel={() => {
            setQuoting(null);
          }}
        />
      )}
      {notice && (
        <p
          role="status"
          className="flex items-center gap-2 border-b border-line bg-surface px-4 py-1.5 text-meta"
        >
          <Check aria-hidden className="size-4 text-success" />
          {notice.kind === "copied" ? (
            t("reader.quote.copied")
          ) : (
            <>
              {t("reader.quote.done", { title: notice.note.title })}
              <Link to={`/notes/${notice.note.id}`} className="text-primary hover:underline">
                {t("reader.quote.open")}
              </Link>
            </>
          )}
        </p>
      )}
      {failure && (
        <p role="alert" className="border-b border-line px-4 py-1.5 text-meta text-danger">
          {t(`errors.${failure instanceof ApiError ? failure.code : "unknown"}`, {
            ...(failure instanceof ApiError ? failure.params : {}),
            defaultValue: t("errors.unknown"),
          })}
        </p>
      )}
      {target.missing && (
        <div
          role="alert"
          className="flex items-center gap-2 border-b border-line bg-surface px-4 py-1.5 text-meta"
        >
          <MapPinOff aria-hidden className="size-4 shrink-0 text-danger" />
          <p className="min-w-0 flex-1">
            {t(target.missing.status === "lost" ? "reader.anchorLost" : "reader.anchorChecking")}{" "}
            {target.missing.quote && (
              <q className="font-serif text-fg-muted italic">{target.missing.quote}</q>
            )}
          </p>
          <Button size="sm" variant="ghost" onClick={target.dismiss}>
            {t("reader.dismiss")}
          </Button>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        {showPanel && (
          <DocumentPanel
            document={document}
            documentKey={attachmentId}
            firstPage={firstPage}
            current={current}
            onGoTo={goToPage}
          />
        )}
        <div
          ref={scroller}
          role="document"
          aria-label={title}
          data-testid="reader-scroller"
          className="min-h-0 min-w-0 flex-1 overflow-auto bg-surface"
        >
          <div
            className="relative mx-auto"
            style={{ height: virtualizer.getTotalSize(), width: Math.max(widest, 1) }}
          >
            {items.map((item) => {
              const page = item.index + 1;
              return (
                <div
                  key={item.key}
                  className="absolute inset-x-0 top-0"
                  style={{ transform: `translateY(${String(item.start)}px)` }}
                >
                  <PageView
                    document={document}
                    pageNumber={page}
                    scale={scale}
                    {...boxOf(page)}
                    onSize={onSize}
                    onText={find.onText}
                    onPoint={(page, point) => {
                      setHovered(
                        point &&
                          annotationAt(
                            byPage.get(page) ?? [],
                            sizes.get(page) ?? firstPage,
                            scale,
                            point,
                          ),
                      );
                    }}
                    onClick={(page, point) => {
                      // A click that ends a selection is not a click on a highlight.
                      if (areaTool || !(getSelection()?.isCollapsed ?? true)) return;
                      const size = sizes.get(page) ?? firstPage;
                      const hit = annotationAt(byPage.get(page) ?? [], size, scale, point);
                      select(hit?.id ?? null);
                      if (hit && !embedded) openPanel();
                    }}
                  >
                    <PageAnnotations
                      annotations={byPage.get(page) ?? []}
                      size={sizes.get(page) ?? firstPage}
                      scale={scale}
                      selectedId={selectedId}
                    />
                    {hovered?.anchor.page === page && hovered.comment !== "" && (
                      <HoverNote
                        annotation={hovered}
                        size={sizes.get(page) ?? firstPage}
                        scale={scale}
                      />
                    )}
                    {areaTool && (
                      <AreaTool
                        label={t("reader.areaToolHint")}
                        size={sizes.get(page) ?? firstPage}
                        scale={scale}
                        onArea={(rect) => {
                          void markArea(page, rect);
                        }}
                      />
                    )}
                    {target.flash?.page === page && (
                      <AnchorFlash
                        anchor={target.flash}
                        size={sizes.get(page) ?? firstPage}
                        scale={scale}
                      />
                    )}
                  </PageView>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
