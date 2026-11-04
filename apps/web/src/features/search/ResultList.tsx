// The deduplicated results. Virtualized with fixed-height rows, so thousands stay smooth and
// the scroll bar stays honest (CLAUDE.md: long lists are virtualized).
import { useVirtualizer } from "@tanstack/react-virtual";
import { FileText, Library, ListChecks, TriangleAlert } from "lucide-react";
import { memo, useRef } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/cn";

import type { SearchResultRow } from "./api";
import { mergeReasons } from "./filters";

export const ROW_HEIGHT = 92;
const OVERSCAN = 5;

interface ResultListProps {
  rows: SearchResultRow[];
  checked: ReadonlySet<string>;
  selectedId: string | null;
  onToggle: (paperId: string) => void;
  onSelect: (paperId: string) => void;
}

export function ResultList({ rows, checked, selectedId, onToggle, onSelect }: ResultListProps) {
  const { t } = useTranslation();
  const scroller = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line react-hooks/incompatible-library -- only skips memoizing this component
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: OVERSCAN,
    getItemKey: (index) => rows[index]?.paper_id ?? index,
  });

  return (
    <div
      ref={scroller}
      role="region"
      aria-label={t("search.results")}
      data-testid="result-scroller"
      className="min-h-0 flex-1 overflow-y-auto"
    >
      <ul
        aria-label={t("search.results")}
        className="relative w-full"
        style={{ height: virtualizer.getTotalSize() }}
      >
        {virtualizer.getVirtualItems().map((item) => {
          const row = rows[item.index];
          if (!row) return null;
          return (
            <li
              key={item.key}
              aria-posinset={item.index + 1}
              aria-setsize={rows.length}
              className="absolute top-0 left-0 w-full"
              style={{ height: ROW_HEIGHT, transform: `translateY(${String(item.start)}px)` }}
            >
              <ResultRow
                row={row}
                checked={checked.has(row.paper_id)}
                selected={selectedId === row.paper_id}
                onToggle={onToggle}
                onSelect={onSelect}
              />
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Memoized: a scroll step then draws only the rows it brings in, not all those on screen.
const ResultRow = memo(function ResultRow({
  row,
  checked,
  selected,
  onToggle,
  onSelect,
}: {
  row: SearchResultRow;
  checked: boolean;
  selected: boolean;
  onToggle: (paperId: string) => void;
  onSelect: (paperId: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const reasons = mergeReasons(row);
  const byline = [
    row.first_author && row.author_count > 1
      ? t("search.andOthers", { name: row.first_author })
      : row.first_author,
    row.year,
    row.venue,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div
      className={cn(
        "flex h-full gap-3 border-b border-line px-4 py-2 hover:bg-hovered",
        selected && "bg-primary-soft",
      )}
    >
      <input
        type="checkbox"
        className="mt-1 size-4 shrink-0"
        checked={checked}
        aria-label={t("search.selectPaper", { title: row.title })}
        onChange={() => {
          onToggle(row.paper_id);
        }}
      />
      <button
        type="button"
        className="min-w-0 flex-1 text-left"
        aria-current={selected || undefined}
        onClick={() => {
          onSelect(row.paper_id);
        }}
      >
        <span className="line-clamp-1 text-ui font-medium text-fg">{row.title}</span>
        <span className="line-clamp-1 text-meta text-fg-muted">{byline}</span>
        <span className="mt-1 flex flex-wrap items-center gap-1">
          {row.sources.map((source) => (
            <Badge key={`${source.source}-${String(source.rank)}`}>
              {t(`search.sourceShort.${source.source}`, { defaultValue: source.source })}
            </Badge>
          ))}
          {row.oa_url && (
            <Badge className="text-success">
              <FileText aria-hidden className="size-3" />
              {t("search.openAccess")}
            </Badge>
          )}
          {row.in_library && (
            <Badge>
              <Library aria-hidden className="size-3" />
              {t("search.inLibrary")}
            </Badge>
          )}
          {row.in_review && (
            <Badge className="text-primary">
              <ListChecks aria-hidden className="size-3" />
              {t("search.inReview")}
            </Badge>
          )}
          {row.is_retracted && (
            <Badge className="text-danger">
              <TriangleAlert aria-hidden className="size-3" />
              {t("search.retracted")}
            </Badge>
          )}
          {reasons.length > 0 && (
            <Badge className="text-primary">
              {t("search.merged", { count: row.sources.length })}
            </Badge>
          )}
        </span>
      </button>
      {row.citation_count !== null && (
        <span className="shrink-0 text-right text-meta text-fg-muted">
          {t("search.citations", {
            count: row.citation_count,
            formatted: row.citation_count.toLocaleString(i18n.language),
          })}
        </span>
      )}
    </div>
  );
});

function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-xs bg-surface px-1.5 text-meta text-fg-muted",
        className,
      )}
    >
      {children}
    </span>
  );
}
