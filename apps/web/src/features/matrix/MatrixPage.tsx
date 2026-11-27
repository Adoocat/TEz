// The literature matrix (design 5.4, Task 52): the included papers against the review's own
// columns. A spreadsheet: edit in place, filter, group by a choice, sort, undo.
import { Plus, Redo2, Undo2 } from "lucide-react";
import type { TFunction } from "i18next";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { useActiveReview, useActiveReviewStore } from "@/features/reviews/store";
import { ApiError } from "@/lib/api/query";

import {
  snapshotOf,
  useCreateMatrix,
  useDeleteColumn,
  useMatrices,
  useMatrix,
  usePutCell,
  type CellValue,
  type ColumnView,
  type MatrixView,
  type RowView,
} from "./api";
import { ColumnDialog } from "./ColumnDialog";
import { ExportMenu } from "./ExportMenu";
import { useMatrixSelection } from "./store";
import {
  MatrixGrid,
  type Density,
  type Edit,
  type GridItem,
  type SortDirection,
} from "./MatrixGrid";
import { CHOICE_TYPES, cellText, groupKeys, matches } from "./values";

// How many edits undo remembers.
const UNDO_DEPTH = 200;

export function MatrixPage() {
  const { t } = useTranslation();
  const review = useActiveReview();
  // A link to a cell (from the reader) names its matrix; its review becomes the active one.
  const [params] = useSearchParams();
  const linked = useMatrix(params.get("matrix"));
  const setActiveReview = useActiveReviewStore((state) => state.setActiveReview);
  const linkedReview = linked.data?.review_id;
  useEffect(() => {
    if (linkedReview && linkedReview !== review?.id) setActiveReview(linkedReview);
  }, [linkedReview, review?.id, setActiveReview]);
  if (!review) {
    return (
      <div className="mx-auto max-w-lg space-y-2 p-6">
        <h1 className="text-h1">{t("matrix.title")}</h1>
        <p className="text-ui text-fg-muted">{t("matrix.noReview")}</p>
        <Link to="/review" className="text-ui text-primary underline">
          {t("matrix.toReview")}
        </Link>
      </div>
    );
  }
  return <Matrices key={review.id} reviewId={review.id} />;
}

function Matrices({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const matrices = useMatrices(reviewId);
  const create = useCreateMatrix(reviewId);
  const [params] = useSearchParams();
  const [chosen, setChosen] = useState<string | null>(() => params.get("matrix"));
  const paper = params.get("paper");
  const column = params.get("column");
  if (!matrices.data) return null;
  const list = matrices.data;
  const current = list.find((m) => m.id === chosen) ?? list[0];
  if (!current) {
    return (
      <div className="mx-auto max-w-lg space-y-3 p-6">
        <h1 className="text-h1">{t("matrix.title")}</h1>
        <p className="text-ui text-fg-muted">{t("matrix.none")}</p>
        <Button
          variant="primary"
          disabled={create.isPending}
          onClick={() => {
            create.mutate(t("matrix.defaultName"), {
              onSuccess: (made) => {
                setChosen(made.id);
              },
            });
          }}
        >
          <Plus aria-hidden />
          {t("matrix.create")}
        </Button>
      </div>
    );
  }
  return (
    <Matrix
      key={current.id}
      matrixId={current.id}
      initial={
        current.id === params.get("matrix") && paper && column
          ? { paperId: paper, columnId: column }
          : null
      }
      others={
        list.length > 1 ? (
          <Segmented
            aria-label={t("matrix.choose")}
            value={current.id}
            options={list.map((m) => ({ value: m.id, label: m.name }))}
            onValueChange={setChosen}
          />
        ) : null
      }
    />
  );
}

interface Change {
  paperId: string;
  columnId: string;
  before: { value: CellValue; keptText: string | null };
  after: { value: CellValue; keptText: string | null };
}

function Matrix({
  matrixId,
  others,
  initial,
}: {
  matrixId: string;
  others: ReactNode;
  initial: { paperId: string; columnId: string } | null;
}) {
  const { t, i18n } = useTranslation();
  const matrix = useMatrix(matrixId);
  const put = usePutCell(matrixId);
  const deleteColumn = useDeleteColumn(matrixId);
  const [filter, setFilter] = useState("");
  const [groupBy, setGroupBy] = useState<string>("");
  const [density, setDensity] = useState<Density>("compact");
  const [showExcluded, setShowExcluded] = useState(false);
  const [sort, setSort] = useState<{ columnId: string; direction: SortDirection } | null>(null);
  const [dialog, setDialog] = useState<{ column: ColumnView | null } | null>(null);
  const [deleting, setDeleting] = useState<ColumnView | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const setCell = useMatrixSelection((state) => state.setCell);
  const onActive = useCallback(
    (cell: { paperId: string; columnId: string } | null) => {
      setCell(cell && { matrixId, ...cell });
    },
    [matrixId, setCell],
  );
  const [history, setHistory] = useState<{ undo: Change[]; redo: Change[] }>({
    undo: [],
    redo: [],
  });

  const data = matrix.data;
  const items = useMemo(
    () =>
      data
        ? itemsOf(data, {
            filter,
            groupBy,
            showExcluded,
            sort,
            t,
            locale: i18n.language,
          })
        : [],
    [data, filter, groupBy, showExcluded, sort, t, i18n.language],
  );

  if (matrix.isError) {
    return (
      <p role="alert" className="p-6 text-ui text-danger">
        {t(`errors.${matrix.error instanceof ApiError ? matrix.error.code : "unknown"}`, {
          defaultValue: t("errors.unknown"),
        })}
      </p>
    );
  }
  if (!data) return null;

  const included = data.rows.filter((row) => row.included);
  const excluded = data.rows.length - included.length;
  const groupable = data.columns.filter(
    (c) => CHOICE_TYPES.includes(c.data_type) || c.data_type === "bool",
  );
  const cellOf = (paperId: string, columnId: string) =>
    data.rows.find((r) => r.paper_id === paperId)?.cells.find((c) => c.column_id === columnId);

  function apply(change: Change, side: "before" | "after") {
    const { value, keptText } = change[side];
    put.mutate({ paperId: change.paperId, columnId: change.columnId, value, keptText });
  }

  function edit({ paperId, columnId, value }: Edit) {
    const before = snapshotOf(cellOf(paperId, columnId));
    if (before.keptText === null && JSON.stringify(before.value) === JSON.stringify(value)) return;
    const change = { paperId, columnId, before, after: { value, keptText: null } };
    setHistory((now) => ({ undo: [...now.undo.slice(-(UNDO_DEPTH - 1)), change], redo: [] }));
    apply(change, "after");
  }

  function stepBack() {
    const change = history.undo.at(-1);
    if (!change) return;
    setHistory((now) => ({ undo: now.undo.slice(0, -1), redo: [...now.redo, change] }));
    apply(change, "before");
  }

  function stepForward() {
    const change = history.redo.at(-1);
    if (!change) return;
    setHistory((now) => ({ undo: [...now.undo, change], redo: now.redo.slice(0, -1) }));
    apply(change, "after");
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2">
        <h1 className="mr-2 text-h2">{data.name}</h1>
        <span className="text-meta text-fg-muted">
          {t("matrix.papers", { count: included.length })} ·{" "}
          {t("matrix.columns", { count: data.columns.length })}
        </span>
        {data.coverage.filled > 0 && (
          <span className="text-meta text-fg-muted" title={t("matrix.coverageHint")}>
            {t("matrix.coverage", {
              percent: Math.round((100 * data.coverage.sourced) / data.coverage.filled),
              sourced: data.coverage.sourced,
              filled: data.coverage.filled,
              rows: data.coverage.rows_sourced,
              of: data.coverage.rows,
            })}
          </span>
        )}
        {others}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            onClick={() => {
              setDialog({ column: null });
            }}
          >
            <Plus aria-hidden />
            {t("matrix.addColumn")}
          </Button>
          <Input
            type="search"
            className="w-48"
            aria-label={t("matrix.filter")}
            placeholder={t("matrix.filter")}
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value);
            }}
          />
          <label className="flex items-center gap-1 text-meta text-fg-muted">
            {t("matrix.groupBy")}
            <select
              className="rounded-md border border-line bg-raised px-2 py-1 text-ui text-fg"
              value={groupBy}
              onChange={(event) => {
                setGroupBy(event.target.value);
              }}
            >
              <option value="">{t("matrix.noGrouping")}</option>
              {groupable.map((column) => (
                <option key={column.id} value={column.id}>
                  {column.name}
                </option>
              ))}
            </select>
          </label>
          <Segmented
            aria-label={t("matrix.density")}
            value={density}
            options={[
              { value: "compact", label: t("matrix.compact") },
              { value: "wide", label: t("matrix.wide") },
            ]}
            onValueChange={setDensity}
          />
          <Button
            size="sm"
            variant="ghost"
            aria-label={t("matrix.undo")}
            disabled={history.undo.length === 0}
            onClick={stepBack}
          >
            <Undo2 aria-hidden />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-label={t("matrix.redo")}
            disabled={history.redo.length === 0}
            onClick={stepForward}
          >
            <Redo2 aria-hidden />
          </Button>
          <ExportMenu matrixId={matrixId} name={data.name} onSaved={setSaved} />
        </div>
      </header>
      {excluded > 0 && (
        <label className="flex items-center gap-2 border-b border-line px-4 py-1.5 text-meta text-fg-muted">
          <input
            type="checkbox"
            checked={showExcluded}
            onChange={(event) => {
              setShowExcluded(event.target.checked);
            }}
          />
          {t("matrix.showExcluded", { count: excluded })}
        </label>
      )}
      {saved && (
        <p role="status" className="border-b border-line px-4 py-1.5 text-meta text-fg-muted">
          {t("matrix.export.saved", { fileName: saved })}
        </p>
      )}
      {put.error && (
        <p role="alert" className="border-b border-line px-4 py-1.5 text-meta text-danger">
          {t(`errors.${put.error instanceof ApiError ? put.error.code : "unknown"}`, {
            defaultValue: t("errors.unknown"),
          })}
        </p>
      )}
      {data.columns.length === 0 ? (
        <p className="p-6 text-ui text-fg-muted">{t("matrix.noColumns")}</p>
      ) : included.length === 0 && !showExcluded ? (
        <p className="p-6 text-ui text-fg-muted">{t("matrix.noRows")}</p>
      ) : (
        <MatrixGrid
          initial={initial}
          onActive={onActive}
          columns={data.columns}
          items={items}
          density={density}
          sort={sort}
          onEdit={edit}
          onUndo={stepBack}
          onRedo={stepForward}
          onSort={(columnId, direction) => {
            setSort({ columnId, direction });
          }}
          onEditColumn={(column) => {
            setDialog({ column });
          }}
          onDeleteColumn={setDeleting}
        />
      )}
      {dialog && (
        <ColumnDialog
          matrixId={matrixId}
          column={dialog.column}
          rows={data.rows}
          onClose={() => {
            setDialog(null);
          }}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        title={t("matrix.deleteColumnTitle", { name: deleting?.name ?? "" })}
        description={t("matrix.deleteColumnText")}
        confirmLabel={t("matrix.deleteColumn")}
        cancelLabel={t("matrix.cancel")}
        onConfirm={() => {
          if (deleting) deleteColumn.mutate(deleting.id);
          // Undo entries for that column have nothing to go back to.
          const gone = deleting?.id;
          setHistory((now) => ({
            undo: now.undo.filter((c) => c.columnId !== gone),
            redo: now.redo.filter((c) => c.columnId !== gone),
          }));
          setDeleting(null);
        }}
        onCancel={() => {
          setDeleting(null);
        }}
      />
    </div>
  );
}

/** The rows to draw: filtered, sorted, and grouped under a choice column when asked. */
export function itemsOf(
  matrix: MatrixView,
  {
    filter,
    groupBy,
    showExcluded,
    sort,
    t,
    locale,
  }: {
    filter: string;
    groupBy: string;
    showExcluded: boolean;
    sort: { columnId: string; direction: SortDirection } | null;
    t: TFunction;
    locale: string;
  },
): GridItem[] {
  const columns = new Map(matrix.columns.map((c) => [c.id, c]));
  const textOf = (row: RowView, columnId: string) => {
    const column = columns.get(columnId);
    const cell = row.cells.find((c) => c.column_id === columnId);
    return column ? cellText(column, cell, t, locale) : "";
  };
  let rows = matrix.rows.filter((row) => row.included || showExcluded);
  if (filter.trim() !== "") {
    rows = rows.filter((row) =>
      matches(
        [row.title, row.first_author ?? "", ...matrix.columns.map((c) => textOf(row, c.id))].join(
          " ",
        ),
        filter,
      ),
    );
  }
  if (sort) {
    const column = columns.get(sort.columnId);
    const collator = new Intl.Collator(locale, { numeric: true, sensitivity: "base" });
    const key = (row: RowView) => {
      const cell = row.cells.find((c) => c.column_id === sort.columnId);
      if (column?.data_type === "number" && typeof cell?.value === "number") return cell.value;
      return textOf(row, sort.columnId);
    };
    rows = [...rows].sort((a, b) => {
      const [x, y] = [key(a), key(b)];
      // Empty cells last, whichever way.
      if (x === "" || y === "") return x === y ? 0 : x === "" ? 1 : -1;
      const order =
        typeof x === "number" && typeof y === "number"
          ? x - y
          : collator.compare(String(x), String(y));
      return sort.direction === "asc" ? order : -order;
    });
  }
  // Excluded papers' rows, kept with their cells, come last.
  rows = [...rows.filter((r) => r.included), ...rows.filter((r) => !r.included)];
  const toItem = (row: RowView): GridItem => ({ kind: "row", key: `row-${row.paper_id}`, row });
  const column = columns.get(groupBy);
  if (!column) return rows.map(toItem);

  const labels = new Map<string, string>([
    ["", t("matrix.emptyGroup")],
    ["yes", t("matrix.yes")],
    ["no", t("matrix.no")],
    ...column.options.map((o) => [o.id, o.label] as [string, string]),
  ]);
  const order = [...column.options.map((o) => o.id), "yes", "no", ""];
  const groups = new Map<string, RowView[]>();
  for (const row of rows) {
    // A paper with several choices stands in each of their groups once: the first one.
    const [first = ""] = groupKeys(
      column,
      row.cells.find((c) => c.column_id === column.id),
    );
    groups.set(first, [...(groups.get(first) ?? []), row]);
  }
  return order.flatMap((key) => {
    const members = groups.get(key);
    if (!members) return [];
    return [
      { kind: "group", key: `group-${key}`, label: labels.get(key) ?? key, count: members.length },
      ...members.map(toItem),
    ];
  });
}
