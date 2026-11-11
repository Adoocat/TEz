// The library (design 4.3): the papers of the chosen collection or tag, organised in place.
// Rows drag onto the sidebar's collections and tags; a selection gets a bulk bar for reading
// status, tags and leaving the current collection.
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/query";
import { cn } from "@/lib/cn";

import {
  readingStatuses,
  useCollections,
  useLibraryPapers,
  useRemoveFromCollection,
  useSetReadingStatus,
  useTagPapers,
  useTags,
  type LibraryPaperRow,
  type ReadingStatus,
  type TagView,
} from "./api";
import { dragPapers } from "./dnd";
import { tagColorVar } from "./LibrarySidebar";
import { useLibraryView } from "./store";

export function LibraryPage() {
  const { t } = useTranslation();
  const { scope, selectedPaperId, selectPaper } = useLibraryView();
  const papers = useLibraryPapers(scope);
  const collections = useCollections();
  const tags = useTags();
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set());
  const rows = useMemo(() => papers.data ?? [], [papers.data]);
  const tagsById = useMemo(
    () => new Map((tags.data ?? []).map((tag) => [tag.id, tag])),
    [tags.data],
  );

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

  // Only rows still in the list count as selected.
  const selected = rows.filter((row) => checked.has(row.id)).map((row) => row.id);
  const allChecked = rows.length > 0 && selected.length === rows.length;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center gap-3 px-4 pt-3 pb-2">
        <h1 className="text-h2">{title}</h1>
        <span className="text-meta text-fg-muted">
          {t("library.paperCount", { count: rows.length })}
        </span>
      </header>
      <div className="flex min-h-10 flex-wrap items-center gap-2 border-y border-line bg-surface px-4 py-1.5">
        <label className="flex items-center gap-2 text-meta">
          <input
            type="checkbox"
            className="size-4"
            aria-label={t("library.selectAll")}
            checked={allChecked}
            disabled={rows.length === 0}
            onChange={() => {
              setChecked(allChecked ? new Set() : new Set(rows.map((row) => row.id)));
            }}
          />
        </label>
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
      ) : (
        <ul aria-label={t("library.papers")} className="min-h-0 flex-1 overflow-auto">
          {rows.map((row) => (
            <PaperItem
              key={row.id}
              row={row}
              tags={tagsById}
              checked={checked.has(row.id)}
              selected={row.id === selectedPaperId}
              dragIds={checked.has(row.id) ? selected : [row.id]}
              onToggle={() => {
                setChecked((current) => {
                  const next = new Set(current);
                  if (!next.delete(row.id)) next.add(row.id);
                  return next;
                });
              }}
              onSelect={() => {
                selectPaper(row.id);
              }}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

export function ReadingDot({ status }: { status: ReadingStatus }) {
  const { t } = useTranslation();
  const color = {
    unread: "var(--color-status-reading-unread)",
    reading: "var(--color-status-reading-active)",
    read: "var(--color-status-reading-done)",
  }[status];
  return (
    <span
      role="img"
      aria-label={t(`library.reading.${status}`)}
      title={t(`library.reading.${status}`)}
      className={cn("size-2 shrink-0 rounded-full", status === "unread" && "border")}
      style={status === "unread" ? { borderColor: color } : { backgroundColor: color }}
    />
  );
}

function PaperItem({
  row,
  tags,
  checked,
  selected,
  dragIds,
  onToggle,
  onSelect,
}: {
  row: LibraryPaperRow;
  tags: Map<string, TagView>;
  checked: boolean;
  selected: boolean;
  dragIds: string[];
  onToggle: () => void;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  return (
    <li
      draggable
      onDragStart={(event) => {
        dragPapers(event, dragIds);
      }}
      aria-selected={selected}
      className={cn(
        "flex h-row items-center gap-2 border-b border-line px-4 text-ui",
        selected ? "bg-primary-soft" : "hover:bg-hovered",
      )}
    >
      <input
        type="checkbox"
        className="size-4"
        aria-label={t("library.selectPaper", { title: row.title })}
        checked={checked}
        onChange={onToggle}
      />
      <ReadingDot status={row.reading_status} />
      <button type="button" className="min-w-0 flex-1 truncate text-left" onClick={onSelect}>
        {row.title}
      </button>
      <span className="flex gap-1">
        {row.tag_ids.map((id) => {
          const tag = tags.get(id);
          return tag ? (
            <span
              key={id}
              title={`#${tag.name}`}
              className="size-2 rounded-full"
              style={{ backgroundColor: tagColorVar(tag.color) }}
            />
          ) : null;
        })}
      </span>
      <span className="w-40 truncate text-meta text-fg-muted">
        {row.first_author
          ? row.author_count > 1
            ? t("search.andOthers", { name: row.first_author })
            : row.first_author
          : ""}
      </span>
      <span className="w-10 text-right text-meta text-fg-muted tabular-nums">{row.year ?? ""}</span>
    </li>
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
