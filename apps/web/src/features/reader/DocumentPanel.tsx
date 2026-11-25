// Left of the document (design 4.5): its outline, or small pictures of its pages.
import { useVirtualizer } from "@tanstack/react-virtual";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { Segmented } from "@/components/ui/segmented";
import { cn } from "@/lib/cn";
import type { OutlineItem, PdfDocument, PdfPageSize } from "@/lib/pdf";

import { useReaderPanel } from "./store";

const THUMBNAIL_WIDTH = 120;
const THUMBNAIL_GAP = 36;

export function DocumentPanel({
  document,
  documentKey,
  firstPage,
  current,
  onGoTo,
}: {
  document: PdfDocument;
  documentKey: string;
  firstPage: PdfPageSize;
  current: number;
  onGoTo: (page: number) => void;
}) {
  const { t } = useTranslation();
  const { tab, setTab } = useReaderPanel();
  return (
    <aside
      aria-label={t("reader.panel")}
      className="flex w-sidebar shrink-0 flex-col border-r border-line bg-surface"
    >
      <div className="p-2">
        <Segmented
          aria-label={t("reader.panel")}
          value={tab}
          options={[
            { value: "outline", label: t("reader.outline") },
            { value: "pages", label: t("reader.pages") },
          ]}
          onValueChange={setTab}
        />
      </div>
      {tab === "outline" ? (
        <Outline document={document} documentKey={documentKey} current={current} onGoTo={onGoTo} />
      ) : (
        <Thumbnails document={document} firstPage={firstPage} current={current} onGoTo={onGoTo} />
      )}
    </aside>
  );
}

interface FlatItem {
  key: string;
  title: string;
  page: number | null;
  depth: number;
}

function flatten(items: OutlineItem[], depth = 0, prefix = ""): FlatItem[] {
  return items.flatMap((item, index) => {
    const key = `${prefix}${String(index)}`;
    return [
      { key, title: item.title, page: item.page, depth },
      ...flatten(item.children, depth + 1, `${key}.`),
    ];
  });
}

function Outline({
  document,
  documentKey,
  current,
  onGoTo,
}: {
  document: PdfDocument;
  documentKey: string;
  current: number;
  onGoTo: (page: number) => void;
}) {
  const { t } = useTranslation();
  const outline = useQuery({
    queryKey: ["reader", "outline", documentKey] as const,
    staleTime: Infinity,
    queryFn: async () => flatten(await document.outline()),
  });
  if (!outline.data) return null;
  if (outline.data.length === 0) {
    return <p className="px-3 py-2 text-meta text-fg-muted">{t("reader.noOutline")}</p>;
  }
  // The section being read: the last one that starts at or before this page.
  const active = outline.data.findLast((item) => item.page !== null && item.page <= current)?.key;
  return (
    <nav aria-label={t("reader.outline")} className="min-h-0 flex-1 overflow-auto pb-2">
      <ul>
        {outline.data.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              disabled={item.page === null}
              aria-current={item.key === active ? "location" : undefined}
              className={cn(
                "flex w-full items-baseline gap-2 px-3 py-1 text-left text-ui text-fg-muted enabled:hover:bg-hovered",
                item.key === active && "bg-primary-soft font-medium text-fg",
              )}
              style={{ paddingInlineStart: `calc(var(--spacing) * ${String(3 + item.depth * 3)})` }}
              onClick={() => {
                if (item.page !== null) onGoTo(item.page);
              }}
            >
              <span className="min-w-0 flex-1 truncate" title={item.title}>
                {item.title}
              </span>
              {item.page !== null && (
                <span className="shrink-0 text-meta tabular-nums">
                  {t("reader.pageShort", { page: item.page })}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function Thumbnails({
  document,
  firstPage,
  current,
  onGoTo,
}: {
  document: PdfDocument;
  firstPage: PdfPageSize;
  current: number;
  onGoTo: (page: number) => void;
}) {
  const { t } = useTranslation();
  const scroller = useRef<HTMLDivElement>(null);
  const height = Math.floor((THUMBNAIL_WIDTH * firstPage.height) / firstPage.width);
  // eslint-disable-next-line react-hooks/incompatible-library -- only skips memoizing this component
  const virtualizer = useVirtualizer({
    count: document.numPages,
    getScrollElement: () => scroller.current,
    estimateSize: () => height + THUMBNAIL_GAP,
    overscan: 2,
  });
  useEffect(() => {
    virtualizer.scrollToIndex(current - 1, { align: "auto" });
  }, [virtualizer, current]);

  return (
    <div ref={scroller} className="min-h-0 flex-1 overflow-auto" data-testid="reader-thumbnails">
      <div className="relative" style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((item) => {
          const page = item.index + 1;
          return (
            <button
              key={item.key}
              type="button"
              aria-label={t("reader.goToPage", { page })}
              aria-current={page === current ? "page" : undefined}
              className="absolute inset-x-0 top-0 flex flex-col items-center gap-1 pt-1"
              style={{ transform: `translateY(${String(item.start)}px)`, height: item.size }}
              onClick={() => {
                onGoTo(page);
              }}
            >
              <Thumbnail
                document={document}
                page={page}
                height={height}
                active={page === current}
              />
              <span className="text-meta text-fg-muted tabular-nums">{page}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Thumbnail({
  document,
  page,
  height,
  active,
}: {
  document: PdfDocument;
  page: number;
  height: number;
  active: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvas.current) return;
    const rendered = document.renderThumbnail(page, canvas.current, THUMBNAIL_WIDTH);
    rendered.done.catch(() => {
      // A page that cannot be drawn stays blank; the page itself says why when it is opened.
      console.warn(`thumbnail of page ${String(page)} could not be drawn`);
    });
    return () => {
      rendered.dispose();
    };
  }, [document, page]);
  return (
    <span
      className={cn(
        "grid place-items-center overflow-hidden border bg-raised",
        active ? "border-primary ring-1 ring-primary" : "border-line",
      )}
      style={{ width: THUMBNAIL_WIDTH, height, colorScheme: "light" }}
    >
      <canvas ref={canvas} aria-hidden className="max-h-full max-w-full" />
    </span>
  );
}
