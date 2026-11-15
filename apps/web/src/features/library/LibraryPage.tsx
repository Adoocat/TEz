// The library (design 4.3): the papers of the chosen scope in a sortable, virtualized table,
// with full-text search, filters and a bulk bar. Selecting a row fills the inspector.
import type { SortingState } from "@tanstack/react-table";
import { Search, X } from "lucide-react";
import { useCallback, useDeferredValue, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/query";

import {
  readingStatuses,
  useCollections,
  useLibraryPapers,
  useLibrarySearch,
  useRemoveFromCollection,
  useSetReadingStatus,
  useTagPapers,
  useTags,
  type TagView,
} from "./api";
import {
  applyFilters,
  isFiltered,
  noLibraryFilters,
  type LibraryFilters,
  type PdfFilter,
} from "./filters";
import { publicationTypes } from "./publicationType";
import { PaperTable } from "./PaperTable";
import { useLibraryView } from "./store";

const DEFAULT_SORT: SortingState = [{ id: "added", desc: true }];

function parseYear(text: string): number | null {
  const value = Number.parseInt(text, 10);
  return Number.isNaN(value) ? null : value;
}

export function LibraryPage() {
  const { t, i18n } = useTranslation();
  const { scope, selectedPaperId, selectPaper } = useLibraryView();
  const papers = useLibraryPapers(scope);
  const collections = useCollections();
  const tags = useTags();
  const [query, setQuery] = useState("");
  // Typing stays responsive; the search follows the deferred text.
  const deferredQuery = useDeferredValue(query);
  const search = useLibrarySearch(deferredQuery);
  const [filters, setFilters] = useState<LibraryFilters>(noLibraryFilters);
  const [sorting, setSorting] = useState<SortingState>(DEFAULT_SORT);
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set());

  const rows = useMemo(() => papers.data ?? [], [papers.data]);
  const searching = deferredQuery.trim() !== "";
  const hitIds = search.data?.paper_ids;
  const visible = useMemo(
    () => applyFilters(rows, filters, searching ? (hitIds ?? []) : null),
    [rows, filters, searching, hitIds],
  );
  const tagsById = useMemo(
    () => new Map((tags.data ?? []).map((tag) => [tag.id, tag])),
    [tags.data],
  );
  const number = (value: number) => value.toLocaleString(i18n.language);

  const title = (() => {
    if (scope.kind === "tag") {
      const tag = tagsById.get(scope.id ?? "");
      return tag ? `#${tag.name}` : "";
    }
    if (scope.kind === "collection") {
      const collection = collections.data?.find((c) => c.id === scope.id);
      if (collection?.is_system) return t("library.inbox");
      return collection?.name ?? "";
    }
    return t("library.allPapers");
  })();

  // Only rows on screen count as selected.
  const selected = useMemo(
    () => visible.filter((row) => checked.has(row.id)).map((row) => row.id),
    [visible, checked],
  );
  const allChecked = visible.length > 0 && selected.length === visible.length;
  const togglePaper = useCallback((paperId: string) => {
    setChecked((current) => {
      const next = new Set(current);
      if (!next.delete(paperId)) next.add(paperId);
      return next;
    });
  }, []);
  const dragIdsFor = useCallback(
    (paperId: string) => (checked.has(paperId) ? selected : [paperId]),
    [checked, selected],
  );

  function changeQuery(text: string) {
    setQuery(text);
    // While searching, rows come best match first unless the user picks a column.
    setSorting(text.trim() ? [] : DEFAULT_SORT);
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 px-4 pt-3 pb-2">
        <h1 className="text-h2">{title}</h1>
        <span aria-live="polite" className="text-meta text-fg-muted">
          {visible.length === rows.length
            ? t("library.paperCount", { count: rows.length })
            : t("library.showing", { shown: number(visible.length), total: number(rows.length) })}
        </span>
        <div className="flex-1" />
        <div className="relative w-72 max-w-full">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-fg-muted"
          />
          <Input
            type="search"
            aria-label={t("library.search")}
            placeholder={t("library.searchPlaceholder")}
            className="pl-8"
            value={query}
            onChange={(event) => {
              changeQuery(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") changeQuery("");
            }}
          />
        </div>
      </header>
      <FilterBar filters={filters} onChange={setFilters} tags={tags.data ?? []} />
      <div className="flex min-h-10 flex-wrap items-center gap-2 border-y border-line bg-surface px-4 py-1">
        <input
          type="checkbox"
          className="size-4"
          aria-label={t("library.selectAll")}
          checked={allChecked}
          disabled={visible.length === 0}
          onChange={() => {
            setChecked(allChecked ? new Set() : new Set(visible.map((row) => row.id)));
          }}
        />
        {selected.length > 0 && (
          <BulkBar
            paperIds={selected}
            tags={tags.data ?? []}
            collectionId={scope.kind === "collection" ? (scope.id ?? null) : null}
          />
        )}
      </div>
      {papers.isSuccess && rows.length === 0 ? (
        <p className="p-6 text-center text-ui text-fg-muted">
          {scope.kind === "all" ? t("library.emptyLibrary") : t("library.emptyScope")}
        </p>
      ) : papers.isSuccess && visible.length === 0 ? (
        <p className="p-6 text-center text-ui text-fg-muted">{t("library.noMatches")}</p>
      ) : (
        <PaperTable
          rows={visible}
          tags={tagsById}
          checked={checked}
          selectedId={selectedPaperId}
          sorting={sorting}
          onSortingChange={setSorting}
          onToggle={togglePaper}
          onSelect={selectPaper}
          dragIdsFor={dragIdsFor}
        />
      )}
    </div>
  );
}

function FilterBar({
  filters,
  onChange,
  tags,
}: {
  filters: LibraryFilters;
  onChange: (filters: LibraryFilters) => void;
  tags: TagView[];
}) {
  const { t } = useTranslation();
  const selectClass = "h-7 rounded-md border border-line bg-raised px-1 text-meta text-fg";
  return (
    <div
      role="group"
      aria-label={t("library.filters")}
      className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-1.5"
    >
      <label className="flex items-center gap-1 text-meta text-fg-muted">
        {t("library.yearFrom")}
        <Input
          className="h-7 w-16"
          inputMode="numeric"
          value={filters.yearFrom ?? ""}
          onChange={(event) => {
            onChange({ ...filters, yearFrom: parseYear(event.target.value) });
          }}
        />
      </label>
      <label className="flex items-center gap-1 text-meta text-fg-muted">
        {t("library.yearTo")}
        <Input
          className="h-7 w-16"
          inputMode="numeric"
          value={filters.yearTo ?? ""}
          onChange={(event) => {
            onChange({ ...filters, yearTo: parseYear(event.target.value) });
          }}
        />
      </label>
      <select
        aria-label={t("library.filterReading")}
        className={selectClass}
        value={filters.reading ?? ""}
        onChange={(event) => {
          const reading = readingStatuses.find((s) => s === event.target.value) ?? null;
          onChange({ ...filters, reading });
        }}
      >
        <option value="">{t("library.anyReading")}</option>
        {readingStatuses.map((status) => (
          <option key={status} value={status}>
            {t(`library.reading.${status}`)}
          </option>
        ))}
      </select>
      <select
        aria-label={t("library.filterTag")}
        className={selectClass}
        value={filters.tagId ?? ""}
        onChange={(event) => {
          onChange({ ...filters, tagId: event.target.value || null });
        }}
      >
        <option value="">{t("library.anyTag")}</option>
        {tags.map((tag) => (
          <option key={tag.id} value={tag.id}>
            #{tag.name}
          </option>
        ))}
      </select>
      <select
        aria-label={t("library.filterType")}
        className={selectClass}
        value={filters.type ?? ""}
        onChange={(event) => {
          const type = publicationTypes.find((value) => value === event.target.value) ?? null;
          onChange({ ...filters, type });
        }}
      >
        <option value="">{t("library.anyType")}</option>
        {publicationTypes.map((type) => (
          <option key={type} value={type}>
            {t(`search.venueTypes.${type}`)}
          </option>
        ))}
      </select>
      <select
        aria-label={t("library.filterPdf")}
        className={selectClass}
        value={filters.pdf}
        onChange={(event) => {
          const pdf = (["any", "has", "none"] as const).find((v) => v === event.target.value);
          onChange({ ...filters, pdf: pdf ?? ("any" satisfies PdfFilter) });
        }}
      >
        <option value="any">{t("library.pdfAny")}</option>
        <option value="has">{t("library.pdfHas")}</option>
        <option value="none">{t("library.pdfNone")}</option>
      </select>
      {isFiltered(filters) && (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            onChange(noLibraryFilters);
          }}
        >
          <X aria-hidden />
          {t("library.clearFilters")}
        </Button>
      )}
    </div>
  );
}

function BulkBar({
  paperIds,
  tags,
  collectionId,
}: {
  paperIds: string[];
  tags: TagView[];
  collectionId: string | null;
}) {
  const { t } = useTranslation();
  const reading = useSetReadingStatus();
  const tag = useTagPapers();
  const leave = useRemoveFromCollection();
  const selectClass = "h-7 rounded-md border border-line bg-raised px-1 text-meta text-fg";
  const failure = reading.error ?? tag.error ?? leave.error;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-meta text-fg-muted">
        {t("library.selected", { count: paperIds.length })}
      </span>
      <select
        aria-label={t("library.setReading")}
        className={selectClass}
        value=""
        onChange={(event) => {
          const status = readingStatuses.find((value) => value === event.target.value);
          if (status) reading.mutate({ paper_ids: paperIds, reading_status: status });
        }}
      >
        <option value="">{t("library.setReading")}</option>
        {readingStatuses.map((status) => (
          <option key={status} value={status}>
            {t(`library.reading.${status}`)}
          </option>
        ))}
      </select>
      <select
        aria-label={t("library.addTag")}
        className={selectClass}
        value=""
        disabled={tags.length === 0}
        onChange={(event) => {
          if (event.target.value) tag.mutate({ id: event.target.value, paperIds });
        }}
      >
        <option value="">{t("library.addTag")}</option>
        {tags.map((item) => (
          <option key={item.id} value={item.id}>
            #{item.name}
          </option>
        ))}
      </select>
      {collectionId && (
        <Button
          size="sm"
          onClick={() => {
            leave.mutate({ id: collectionId, paperIds });
          }}
        >
          {t("library.removeFromCollection")}
        </Button>
      )}
      {failure && (
        <span role="alert" className="text-meta text-danger">
          {t(`errors.${failure instanceof ApiError ? failure.code : "unknown"}`, {
            defaultValue: t("errors.unknown"),
          })}
        </span>
      )}
    </div>
  );
}
