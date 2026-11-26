// The matrix as a spreadsheet (design 5.4, Task 52): headers stay in place both ways, rows are
// drawn only when in view, and everything works from the keyboard.
//
// Keys (grid focused): arrows, Tab and Shift+Tab, Home and End move; Enter or F2 edits; typing
// into a text or number cell starts editing with that key; Delete clears; Space flips yes/no.
// While editing: Enter keeps and goes down, Tab keeps and goes right, Escape drops the edit.
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  AlertTriangle,
  ChevronDown,
  Link2,
  CircleDot,
  Hash,
  ListChecks,
  ToggleLeft,
  Type,
  type LucideIcon,
} from "lucide-react";
import { DropdownMenu } from "radix-ui";
import type { TFunction } from "i18next";
import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/cn";

import type { CellValue, CellView, ColumnView, DataType, RowView } from "./api";
import { CellEditor } from "./CellEditor";
import { cellText } from "./values";

export const TYPE_ICONS: Record<DataType, LucideIcon> = {
  text: Type,
  number: Hash,
  enum: CircleDot,
  multi_enum: ListChecks,
  bool: ToggleLeft,
};

export type Density = "compact" | "wide";
const ROW_HEIGHT: Record<Density, number> = { compact: 36, wide: 72 };
const COLUMN_WIDTH: Record<Density, number> = { compact: 200, wide: 300 };
const GROUP_HEIGHT = 32;
const HEADER_HEIGHT = 40;
const FIRST_WIDTH = 280;
const OVERSCAN = 8;

export type GridItem =
  | { kind: "group"; key: string; label: string; count: number }
  | { kind: "row"; key: string; row: RowView };

export interface Edit {
  paperId: string;
  columnId: string;
  value: CellValue;
}

export type SortDirection = "asc" | "desc";

interface GridProps {
  columns: ColumnView[];
  items: GridItem[];
  density: Density;
  sort: { columnId: string; direction: SortDirection } | null;
  onEdit: (edit: Edit) => void;
  onUndo: () => void;
  onRedo: () => void;
  onSort: (columnId: string, direction: SortDirection) => void;
  onEditColumn: (column: ColumnView) => void;
  onDeleteColumn: (column: ColumnView) => void;
  /** The cell to start on, e.g. one the reader linked back to. */
  initial?: { paperId: string; columnId: string } | null;
  /** Told whenever the active cell changes. */
  onActive?: (cell: { paperId: string; columnId: string } | null) => void;
}

interface Position {
  paperId: string;
  column: number;
}

const cellId = (paperId: string, columnId: string) => `matrix-cell-${paperId}-${columnId}`;

export function MatrixGrid({
  columns,
  items,
  density,
  sort,
  onEdit,
  onUndo,
  onRedo,
  onSort,
  onEditColumn,
  onDeleteColumn,
  initial = null,
  onActive,
}: GridProps) {
  const { t, i18n } = useTranslation();
  const scroller = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<Position | null>(() => {
    const column = columns.findIndex((c) => c.id === initial?.columnId);
    return initial && column !== -1 ? { paperId: initial.paperId, column } : null;
  });
  const [editing, setEditing] = useState<{ start: string | null } | null>(null);

  const { rows, rowIndex, itemIndex } = useMemo(() => {
    const rows = items.flatMap((item) => (item.kind === "row" ? [item.row] : []));
    return {
      rows,
      rowIndex: new Map(rows.map((row, index) => [row.paper_id, index])),
      itemIndex: new Map(items.map((item, index) => [item.key, index])),
    };
  }, [items]);
  // Stable, so a row that did not change is not drawn again while scrolling.
  const pick = useCallback((paperId: string, column: number, edit: boolean, included: boolean) => {
    setActive({ paperId, column });
    setEditing(edit && included ? { start: null } : null);
  }, []);
  const width = COLUMN_WIDTH[density];
  const template = `${String(FIRST_WIDTH)}px repeat(${String(columns.length)}, ${String(width)}px)`;
  // The rows are positioned absolutely, so their box gets its width from here.
  const fullWidth = FIRST_WIDTH + columns.length * width;

  // eslint-disable-next-line react-hooks/incompatible-library -- the virtualizer keeps its own state
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => scroller.current,
    estimateSize: (index) => (items[index]?.kind === "group" ? GROUP_HEIGHT : ROW_HEIGHT[density]),
    overscan: OVERSCAN,
    getItemKey: (index) => items[index]?.key ?? index,
    scrollMargin: HEADER_HEIGHT,
  });
  useEffect(() => {
    virtualizer.measure();
  }, [density, virtualizer]);

  // The active cell stays on a row that is shown; the first one when there is none.
  const current =
    active && rowIndex.has(active.paperId) && active.column < columns.length ? active : null;
  const currentRow = current ? rows[rowIndex.get(current.paperId) ?? 0] : undefined;
  const currentColumn = current ? columns[current.column] : undefined;
  const activePaper = currentRow?.paper_id;
  const activeColumnId = currentColumn?.id;
  useEffect(() => {
    onActive?.(
      activePaper && activeColumnId ? { paperId: activePaper, columnId: activeColumnId } : null,
    );
  }, [activePaper, activeColumnId, onActive]);
  // A cell asked for from elsewhere is brought into view once the rows are there.
  const shown = useRef(false);
  useEffect(() => {
    if (shown.current || !initial) return;
    const index = itemIndex.get(`row-${initial.paperId}`);
    if (index === undefined) return;
    shown.current = true;
    virtualizer.scrollToIndex(index, { align: "center" });
    scroller.current?.focus();
  }, [initial, itemIndex, virtualizer]);

  function moveTo(paperId: string, column: number) {
    setActive({ paperId, column });
    setEditing(null);
    const index = itemIndex.get(`row-${paperId}`);
    if (index !== undefined) virtualizer.scrollToIndex(index, { align: "auto" });
    const left = FIRST_WIDTH + column * width;
    const view = scroller.current;
    if (view) {
      if (left < view.scrollLeft + FIRST_WIDTH) view.scrollLeft = left - FIRST_WIDTH;
      else if (left + width > view.scrollLeft + view.clientWidth) {
        view.scrollLeft = left + width - view.clientWidth;
      }
    }
  }

  function move(rowsBy: number, columnsBy: number) {
    if (rows.length === 0 || columns.length === 0) return;
    if (!current) {
      const first = rows[0];
      if (first) moveTo(first.paper_id, 0);
      return;
    }
    const at = rowIndex.get(current.paperId) ?? 0;
    const next = rows[Math.min(Math.max(at + rowsBy, 0), rows.length - 1)];
    const column = Math.min(Math.max(current.column + columnsBy, 0), columns.length - 1);
    if (next) moveTo(next.paper_id, column);
  }

  /** Tab order runs along a row, then to the next row's first cell. */
  function step(forward: boolean) {
    const last = columns.length - 1;
    if (!current) move(0, 0);
    else if (forward && current.column === last) move(1, -last);
    else if (!forward && current.column === 0) move(-1, last);
    else move(0, forward ? 1 : -1);
  }

  const editable = (row: RowView | undefined) => row?.included === true;

  function write(value: CellValue) {
    if (!currentRow || !currentColumn || !editable(currentRow)) return;
    onEdit({ paperId: currentRow.paper_id, columnId: currentColumn.id, value });
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (editing) return;
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key;
    if (mod && key.toLowerCase() === "z") {
      event.preventDefault();
      if (event.shiftKey) onRedo();
      else onUndo();
      return;
    }
    if (mod && key.toLowerCase() === "y") {
      event.preventDefault();
      onRedo();
      return;
    }
    const moves: Record<string, () => void> = {
      ArrowDown: () => {
        move(1, 0);
      },
      ArrowUp: () => {
        move(-1, 0);
      },
      ArrowRight: () => {
        move(0, 1);
      },
      ArrowLeft: () => {
        move(0, -1);
      },
      PageDown: () => {
        move(10, 0);
      },
      PageUp: () => {
        move(-10, 0);
      },
      Home: () => {
        if (mod) move(-rows.length, -columns.length);
        else move(0, -columns.length);
      },
      End: () => {
        if (mod) move(rows.length, columns.length);
        else move(0, columns.length);
      },
      Tab: () => {
        step(!event.shiftKey);
      },
    };
    const moving = moves[key];
    if (moving) {
      // Tab leaves the grid from its edges, as elsewhere.
      if (key === "Tab" && current) {
        const at = rowIndex.get(current.paperId) ?? 0;
        const atEnd =
          !event.shiftKey && at === rows.length - 1 && current.column === columns.length - 1;
        const atStart = event.shiftKey && at === 0 && current.column === 0;
        if (atEnd || atStart) return;
      }
      event.preventDefault();
      moving();
      return;
    }
    if (!current || !currentColumn || !editable(currentRow)) return;
    const type = currentColumn.data_type;
    if (key === "Enter" || key === "F2") {
      event.preventDefault();
      setEditing({ start: null });
    } else if (key === "Delete" || key === "Backspace") {
      event.preventDefault();
      write(null);
    } else if (key === " " && type === "bool") {
      event.preventDefault();
      const now = currentRow?.cells.find((c) => c.column_id === currentColumn.id)?.value;
      write(now !== true);
    } else if (
      key.length === 1 &&
      !mod &&
      !event.altKey &&
      (type === "text" || type === "number")
    ) {
      event.preventDefault();
      setEditing({ start: key });
    }
  }

  const activeId =
    currentRow && currentColumn ? cellId(currentRow.paper_id, currentColumn.id) : undefined;

  return (
    <div
      ref={scroller}
      role="grid"
      tabIndex={0}
      aria-label={t("matrix.grid")}
      aria-rowcount={rows.length + 1}
      aria-colcount={columns.length + 1}
      aria-activedescendant={editing ? undefined : activeId}
      data-testid="matrix-scroller"
      className="relative min-h-0 flex-1 overflow-auto text-ui outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onKeyDown={onKeyDown}
      onFocus={() => {
        if (!current) move(0, 0);
      }}
    >
      <div
        role="row"
        aria-rowindex={1}
        className="sticky top-0 z-[var(--z-sticky)] grid w-max border-b border-line bg-surface"
        style={{ gridTemplateColumns: template, height: HEADER_HEIGHT }}
      >
        <div
          role="columnheader"
          className="sticky left-0 z-[var(--z-sticky)] flex items-center border-r border-line bg-surface px-3 text-meta font-medium text-fg-muted"
        >
          {t("matrix.paper")}
        </div>
        {columns.map((column) => (
          <ColumnHeader
            key={column.id}
            column={column}
            sorted={sort?.columnId === column.id ? sort.direction : null}
            onSort={onSort}
            onEdit={onEditColumn}
            onDelete={onDeleteColumn}
          />
        ))}
      </div>
      <div
        role="rowgroup"
        className="relative"
        style={{ height: virtualizer.getTotalSize(), width: fullWidth }}
      >
        {virtualizer.getVirtualItems().map((virtual) => {
          const item = items[virtual.index];
          if (!item) return null;
          const top = virtual.start - HEADER_HEIGHT;
          if (item.kind === "group") {
            return (
              <div
                key={item.key}
                role="row"
                className="absolute left-0 flex w-full items-center border-b border-line bg-surface px-3 text-meta font-medium whitespace-nowrap text-fg-muted"
                style={{ top, height: GROUP_HEIGHT }}
              >
                <span role="rowheader" className="sticky left-3">
                  {item.label} · {item.count}
                </span>
              </div>
            );
          }
          const row = item.row;
          const activeColumn = current?.paperId === row.paper_id ? current.column : null;
          return (
            <MatrixRow
              key={item.key}
              row={row}
              rowIndex={(rowIndex.get(row.paper_id) ?? 0) + 2}
              columns={columns}
              template={template}
              top={top}
              height={ROW_HEIGHT[density]}
              wide={density === "wide"}
              activeColumn={activeColumn}
              locale={i18n.language}
              t={t}
              onPick={pick}
              editor={
                activeColumn !== null && editing && currentColumn ? (
                  <CellEditor
                    column={currentColumn}
                    cell={row.cells.find((c) => c.column_id === currentColumn.id)}
                    start={editing.start}
                    onDone={(result) => {
                      setEditing(null);
                      if (result.kind === "keep") write(result.value);
                      if (result.kind !== "cancel" && result.then === "down") move(1, 0);
                      if (result.kind !== "cancel" && result.then === "right") step(true);
                      scroller.current?.focus();
                    }}
                  />
                ) : null
              }
            />
          );
        })}
      </div>
    </div>
  );
}

function ColumnHeader({
  column,
  sorted,
  onSort,
  onEdit,
  onDelete,
}: {
  column: ColumnView;
  sorted: SortDirection | null;
  onSort: (columnId: string, direction: SortDirection) => void;
  onEdit: (column: ColumnView) => void;
  onDelete: (column: ColumnView) => void;
}) {
  const { t } = useTranslation();
  const Icon = TYPE_ICONS[column.data_type];
  return (
    <div
      role="columnheader"
      aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : undefined}
      title={column.instruction ?? undefined}
      className="flex min-w-0 items-center gap-1.5 border-r border-line px-3 text-meta font-medium text-fg"
    >
      <Icon
        aria-label={t(`matrix.types.${column.data_type}`)}
        className="size-3.5 shrink-0 text-fg-muted"
      />
      <span className="truncate">{column.name}</span>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger
          aria-label={t("matrix.columnMenu", { name: column.name })}
          className="ml-auto grid size-6 shrink-0 place-items-center rounded-xs text-fg-muted hover:bg-hovered hover:text-fg"
        >
          <ChevronDown aria-hidden className="size-3.5" />
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            className="z-[var(--z-popover)] min-w-44 rounded-md border border-line bg-raised p-1 text-ui shadow-popover"
          >
            {[
              {
                label: t("matrix.editColumn"),
                run: () => {
                  onEdit(column);
                },
              },
              {
                label: t("matrix.sortAsc"),
                run: () => {
                  onSort(column.id, "asc");
                },
              },
              {
                label: t("matrix.sortDesc"),
                run: () => {
                  onSort(column.id, "desc");
                },
              },
              {
                label: t("matrix.deleteColumn"),
                run: () => {
                  onDelete(column);
                },
                danger: true,
              },
            ].map((entry) => (
              <DropdownMenu.Item
                key={entry.label}
                className={cn(
                  "cursor-default rounded-xs px-2 py-1.5 outline-none data-highlighted:bg-hovered",
                  entry.danger && "text-danger",
                )}
                onSelect={entry.run}
              >
                {entry.label}
              </DropdownMenu.Item>
            ))}
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  );
}

// Memoized: scrolling draws only the rows it brings in, and editing one cell redraws one row.
const MatrixRow = memo(function MatrixRow({
  row,
  rowIndex,
  columns,
  template,
  top,
  height,
  wide,
  activeColumn,
  locale,
  t,
  onPick,
  editor,
}: {
  row: RowView;
  rowIndex: number;
  columns: ColumnView[];
  template: string;
  top: number;
  height: number;
  wide: boolean;
  activeColumn: number | null;
  locale: string;
  t: TFunction;
  onPick: (paperId: string, column: number, edit: boolean, included: boolean) => void;
  editor: ReactNode;
}) {
  const cells = new Map(row.cells.map((cell) => [cell.column_id, cell]));
  const citation = [row.first_author, row.year].filter(Boolean).join(" · ");
  return (
    <div
      role="row"
      aria-rowindex={rowIndex}
      className={cn(
        // Each row lays itself out and paints alone: scrolling adds rows, it does not redo others.
        "absolute left-0 grid border-b border-line [contain:layout_paint]",
        row.included ? "bg-raised" : "bg-surface text-fg-muted",
      )}
      style={{ top, height, gridTemplateColumns: template }}
    >
      <div
        role="rowheader"
        // Above the cells it slides over when the grid scrolls sideways.
        className="sticky left-0 z-[var(--z-sticky)] flex min-w-0 flex-col justify-center border-r border-line bg-inherit px-3"
      >
        <span className={cn("font-medium text-fg", wide ? "line-clamp-2" : "truncate")}>
          {row.title}
        </span>
        <span className="truncate text-meta text-fg-muted">
          {citation}
          {citation && " · "}
          {t(`library.reading.${row.reading_status}`)}
          {!row.included && ` · ${t("matrix.excluded")}`}
        </span>
      </div>
      {columns.map((column, index) => (
        <Cell
          key={column.id}
          id={cellId(row.paper_id, column.id)}
          column={column}
          cell={cells.get(column.id)}
          active={activeColumn === index}
          readOnly={!row.included}
          wide={wide}
          locale={locale}
          t={t}
          onPick={(edit) => {
            onPick(row.paper_id, index, edit, row.included);
          }}
        >
          {activeColumn === index ? editor : null}
        </Cell>
      ))}
    </div>
  );
});

function Cell({
  id,
  column,
  cell,
  active,
  readOnly,
  wide,
  locale,
  t,
  onPick,
  children,
}: {
  id: string;
  column: ColumnView;
  cell: CellView | undefined;
  active: boolean;
  readOnly: boolean;
  wide: boolean;
  locale: string;
  t: TFunction;
  onPick: (edit: boolean) => void;
  children: ReactNode;
}) {
  const kept = cell?.kept_text != null;
  const text = cellText(column, cell, t, locale);
  const sources = cell?.evidence.length ?? 0;
  return (
    <div
      id={id}
      role="gridcell"
      aria-selected={active}
      aria-readonly={readOnly || undefined}
      aria-invalid={kept || undefined}
      className={cn(
        "relative flex min-w-0 items-center gap-1 border-r border-line px-3",
        column.data_type === "number" && !kept && "justify-end tabular-nums",
        active && "outline-2 -outline-offset-2 outline-primary",
        kept && "text-warning italic",
      )}
      onMouseDown={(event) => {
        // A click in the open editor is the editor's.
        if (children) return;
        // Keep the focus on the grid, so the keys keep working.
        event.preventDefault();
        onPick(false);
      }}
      onDoubleClick={() => {
        onPick(true);
      }}
    >
      {kept && (
        <AlertTriangle aria-label={t("matrix.kept")} className="size-3.5 shrink-0 text-warning" />
      )}
      <span className={cn(wide ? "line-clamp-3" : "truncate")}>{text}</span>
      {sources > 0 && (
        <Link2
          aria-label={t("matrix.evidence.sources", { count: sources })}
          className="absolute top-1 right-1 size-3 text-primary"
        />
      )}
      {children}
    </div>
  );
}
