// The library table (design 4.3, list view): sortable columns, virtualized rows, so 2000+
// papers scroll smoothly (CLAUDE.md). Rows drag onto the sidebar's collections and tags.
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown,
  ArrowUp,
  FileCheck2,
  FileText,
  FileWarning,
  FileX2,
  Loader2,
} from "lucide-react";
import { memo, useMemo, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useLayoutStore } from "@/app/layout/uiStore";
import { cn } from "@/lib/cn";
import { useShortcuts } from "@/lib/shortcuts/useShortcuts";

import type { LibraryPaperRow, TagView } from "./api";
import { dragPapers } from "./dnd";
import { ReadingDot } from "./ReadingDot";
import { tagColorVar } from "./tagColor";

export const TABLE_ROW_HEIGHT = 32;
const OVERSCAN = 10;
// Column widths, shared by the header and every row (CSS grid).
const GRID =
  "grid min-w-[56rem] grid-cols-[2rem_1.25rem_minmax(12rem,1fr)_8.5rem_3rem_8rem_3.5rem_1.5rem_6rem_8rem] items-center gap-x-2";

const readingOrder = { unread: 0, reading: 1, read: 2 } as const;
const pdfOrder = { ok: 0, needs_ocr: 1, pending: 2, failed: 3, none: 4 } as const;

interface PaperTableProps {
  rows: LibraryPaperRow[];
  tags: Map<string, TagView>;
  checked: ReadonlySet<string>;
  selectedId: string | null;
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onToggle: (paperId: string) => void;
  onSelect: (paperId: string) => void;
  /** Enter on the selected row: open its PDF. */
  onOpen: (paperId: string) => void;
  /** The ids a drag starting on this row carries: the selection if the row is in it. */
  dragIdsFor: (paperId: string) => string[];
}

export function PaperTable({
  rows,
  tags,
  checked,
  selectedId,
  sorting,
  onSortingChange,
  onToggle,
  onSelect,
  onOpen,
  dragIdsFor,
}: PaperTableProps) {
  const { t, i18n } = useTranslation();
  const scroller = useRef<HTMLDivElement>(null);

  const columns = useMemo<ColumnDef<LibraryPaperRow>[]>(
    () => [
      { id: "select", enableSorting: false, header: () => null },
      {
        id: "reading",
        header: () => <span className="sr-only">{t("library.columns.reading")}</span>,
        accessorFn: (row) => readingOrder[row.reading_status],
      },
      {
        id: "title",
        header: t("library.columns.title"),
        accessorFn: (row) => row.title.toLocaleLowerCase(i18n.language),
      },
      {
        id: "authors",
        header: t("library.columns.authors"),
        accessorFn: (row) => row.first_author?.toLocaleLowerCase(i18n.language) ?? "",
        sortUndefined: "last",
      },
      {
        id: "year",
        header: t("library.columns.year"),
        accessorFn: (row) => row.year ?? undefined,
        sortUndefined: "last",
      },
      {
        id: "venue",
        header: t("library.columns.venue"),
        accessorFn: (row) => row.venue?.toLocaleLowerCase(i18n.language) ?? undefined,
        sortUndefined: "last",
      },
      { id: "tags", header: t("library.columns.tags"), enableSorting: false },
      {
        id: "pdf",
        header: () => <span className="sr-only">{t("library.columns.pdf")}</span>,
        accessorFn: (row) => pdfOrder[row.pdf],
      },
      {
        id: "added",
        header: t("library.columns.added"),
        accessorFn: (row) => row.added_at ?? "",
        sortDescFirst: true,
      },
      {
        id: "citekey",
        header: t("library.columns.citekey"),
        accessorFn: (row) => row.citekey ?? undefined,
        sortUndefined: "last",
      },
    ],
    [t, i18n.language],
  );

  // eslint-disable-next-line react-hooks/incompatible-library -- the table keeps its own state
  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: (updater) => {
      onSortingChange(typeof updater === "function" ? updater(sorting) : updater);
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    // Ascending first, whatever the value type; "added" asks for newest first itself.
    sortDescFirst: false,
    getRowId: (row) => row.id,
  });
  const sortedRows = table.getRowModel().rows;

  const virtualizer = useVirtualizer({
    count: sortedRows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => TABLE_ROW_HEIGHT,
    overscan: OVERSCAN,
    getItemKey: (index) => sortedRows[index]?.id ?? index,
    // The sticky header sits above the rows inside the same scroller.
    scrollMargin: TABLE_ROW_HEIGHT,
  });
  const toggleInspector = useLayoutStore((state) => state.toggleInspector);
  // The list context (design-prompt §6): arrows move the selection, Space shows or hides the
  // inspector, Enter opens the PDF.
  function move(by: 1 | -1) {
    const at = sortedRows.findIndex((row) => row.id === selectedId);
    const index = at === -1 ? 0 : Math.min(Math.max(at + by, 0), sortedRows.length - 1);
    const row = sortedRows[index];
    if (!row) return;
    onSelect(row.id);
    virtualizer.scrollToIndex(index);
  }
  useShortcuts("list", {
    down: () => {
      move(1);
    },
    up: () => {
      move(-1);
    },
    preview: toggleInspector,
    open: () => {
      if (selectedId !== null) onOpen(selectedId);
    },
  });

  const dateFormat = useMemo(
    () => new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }),
    [i18n.language],
  );

  return (
    // One scroller for both axes: on a narrow window the columns scroll sideways, header with
    // them, instead of pushing the inspector off screen.
    <div
      ref={scroller}
      role="table"
      aria-label={t("library.papers")}
      aria-rowcount={sortedRows.length + 1}
      data-testid="library-scroller"
      className="min-h-0 flex-1 overflow-auto text-ui"
    >
      <div
        role="rowgroup"
        className="sticky top-0 z-[var(--z-sticky)] w-max min-w-full border-b border-line bg-surface"
      >
        {table.getHeaderGroups().map((group) => (
          <div
            key={group.id}
            role="row"
            className={cn(GRID, "px-4 text-meta text-fg-muted")}
            style={{ height: TABLE_ROW_HEIGHT }}
          >
            {group.headers.map((header) => {
              const sorted = header.column.getIsSorted();
              const content = flexRender(header.column.columnDef.header, header.getContext());
              return (
                <div
                  key={header.id}
                  role="columnheader"
                  aria-sort={
                    sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined
                  }
                  className="min-w-0"
                >
                  {header.column.getCanSort() ? (
                    <button
                      type="button"
                      className="flex items-center gap-1 truncate hover:text-fg"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {content}
                      {sorted === "asc" && <ArrowUp aria-hidden className="size-3" />}
                      {sorted === "desc" && <ArrowDown aria-hidden className="size-3" />}
                    </button>
                  ) : (
                    content
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div role="rowgroup" className="w-max min-w-full">
        <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((item) => {
            const row = sortedRows[item.index]?.original;
            if (!row) return null;
            return (
              <PaperRow
                key={item.key}
                row={row}
                index={item.index}
                start={item.start - TABLE_ROW_HEIGHT}
                tags={tags}
                checked={checked.has(row.id)}
                selected={row.id === selectedId}
                added={row.added_at ? dateFormat.format(new Date(row.added_at)) : ""}
                onToggle={onToggle}
                onSelect={onSelect}
                dragIdsFor={dragIdsFor}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Memoized: a scroll step draws only the rows it brings in.
const PaperRow = memo(function PaperRow({
  row,
  index,
  start,
  tags,
  checked,
  selected,
  added,
  onToggle,
  onSelect,
  dragIdsFor,
}: {
  row: LibraryPaperRow;
  index: number;
  start: number;
  tags: Map<string, TagView>;
  checked: boolean;
  selected: boolean;
  added: string;
  onToggle: (paperId: string) => void;
  onSelect: (paperId: string) => void;
  dragIdsFor: (paperId: string) => string[];
}) {
  const { t } = useTranslation();
  const authors = row.first_author
    ? row.author_count > 1
      ? t("search.andOthers", { name: row.first_author })
      : row.first_author
    : "";
  return (
    <div
      role="row"
      aria-rowindex={index + 2}
      aria-selected={selected}
      draggable
      onDragStart={(event) => {
        dragPapers(event, dragIdsFor(row.id));
      }}
      onClick={() => {
        onSelect(row.id);
      }}
      className={cn(
        GRID,
        "absolute top-0 left-0 w-full cursor-default border-b border-line px-4",
        selected ? "bg-primary-soft" : "hover:bg-hovered",
      )}
      style={{ height: TABLE_ROW_HEIGHT, transform: `translateY(${String(start)}px)` }}
    >
      <Cell>
        <input
          type="checkbox"
          className="size-4"
          aria-label={t("library.selectPaper", { title: row.title })}
          checked={checked}
          onClick={(event) => {
            event.stopPropagation();
          }}
          onChange={() => {
            onToggle(row.id);
          }}
        />
      </Cell>
      <Cell>
        <ReadingDot status={row.reading_status} />
      </Cell>
      <Cell className="truncate" title={row.title}>
        {row.title}
      </Cell>
      <Cell className="truncate text-meta text-fg-muted">{authors}</Cell>
      <Cell className="text-meta text-fg-muted tabular-nums">{row.year ?? ""}</Cell>
      <Cell className="truncate text-meta text-fg-muted" title={row.venue ?? undefined}>
        {row.venue ?? ""}
      </Cell>
      <Cell className="flex gap-1">
        {row.tag_ids.map((id) => {
          const tag = tags.get(id);
          return tag ? (
            <span
              key={id}
              role="img"
              aria-label={`#${tag.name}`}
              title={`#${tag.name}`}
              className="size-2 shrink-0 rounded-full"
              style={{ backgroundColor: tagColorVar(tag.color) }}
            />
          ) : null;
        })}
      </Cell>
      <Cell>
        <PdfIcon state={row.pdf} />
      </Cell>
      <Cell className="truncate text-meta text-fg-muted">{added}</Cell>
      <Cell className="truncate font-mono text-meta text-fg-muted">{row.citekey ?? ""}</Cell>
    </div>
  );
});

function Cell({
  children,
  className,
  title,
}: {
  children?: ReactNode;
  className?: string;
  title?: string | undefined;
}) {
  return (
    <div role="cell" className={cn("min-w-0", className)} title={title}>
      {children}
    </div>
  );
}

export function PdfIcon({ state }: { state: LibraryPaperRow["pdf"] }) {
  const { t } = useTranslation();
  const label = t(`library.pdf.${state}`);
  const icon = {
    none: <FileX2 className="size-4 text-fg-muted/50" />,
    pending: <Loader2 className="size-4 animate-spin text-fg-muted" />,
    ok: <FileCheck2 className="size-4 text-success" />,
    needs_ocr: <FileText className="size-4 text-warning" />,
    failed: <FileWarning className="size-4 text-danger" />,
  }[state];
  return (
    <span role="img" aria-label={label} title={label}>
      {icon}
    </span>
  );
}
