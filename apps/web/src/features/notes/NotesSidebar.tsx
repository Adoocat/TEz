// The notes screen's left side (design 5.3): new note, search, and the tree.
import { FilePlus2, FileText, Plus, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";

import { useCreateNote, useNotes, useNoteSearch } from "./api";
import { treeOf } from "./tree";

export function NotesSidebar() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const notes = useNotes();
  const create = useCreateNote();
  const [query, setQuery] = useState("");
  const deferred = useDeferredValue(query);
  const search = useNoteSearch(deferred);
  const searching = deferred.trim() !== "";

  function add(parentId: string | null) {
    create.mutate(
      { title: t("notes.untitled"), parent_id: parentId },
      { onSuccess: (note) => void navigate(`/notes/${note.id}`) },
    );
  }

  const itemClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      "flex min-w-0 flex-1 items-center gap-2 rounded-md py-1 pr-1 text-ui text-fg hover:bg-hovered",
      isActive && "bg-primary-soft font-medium",
    );

  return (
    <nav aria-label={t("nav.notes")} className="flex h-full flex-col gap-2 p-2">
      <Button
        variant="primary"
        disabled={create.isPending}
        onClick={() => {
          add(null);
        }}
      >
        <Plus aria-hidden />
        {t("notes.new")}
      </Button>
      <div className="relative">
        <Search
          aria-hidden
          className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-fg-muted"
        />
        <Input
          type="search"
          className="pl-8"
          aria-label={t("notes.search")}
          placeholder={t("notes.search")}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") setQuery("");
          }}
        />
      </div>
      {searching ? (
        <ul aria-label={t("notes.results")} className="min-h-0 flex-1 space-y-1 overflow-auto">
          {search.isSuccess && search.data.length === 0 && (
            <li className="px-2 text-meta text-fg-muted">{t("notes.noResults")}</li>
          )}
          {(search.data ?? []).map((hit) => (
            <li key={hit.note_id}>
              <NavLink
                to={`/notes/${hit.note_id}`}
                className="block rounded-md px-2 py-1 hover:bg-hovered"
              >
                <span className="block truncate text-ui font-medium text-fg">{hit.title}</span>
                <span className="line-clamp-2 text-meta text-fg-muted">
                  {hit.passage.map((part, index) =>
                    part.hit ? (
                      <mark
                        // The parts of a passage never change order.
                        key={index}
                        className="rounded-xs bg-[color-mix(in_srgb,var(--color-highlight-yellow)_45%,transparent)] text-fg"
                      >
                        {part.text}
                      </mark>
                    ) : (
                      <span key={index}>{part.text}</span>
                    ),
                  )}
                </span>
              </NavLink>
            </li>
          ))}
        </ul>
      ) : (
        <ul aria-label={t("notes.tree")} className="min-h-0 flex-1 overflow-auto">
          {notes.isSuccess && notes.data.length === 0 && (
            <li className="px-2 text-meta text-fg-muted">{t("notes.none")}</li>
          )}
          {treeOf(notes.data ?? [], i18n.language).map(({ note, depth }) => (
            <li
              key={note.id}
              className="group flex items-center gap-1"
              style={{ paddingInlineStart: `calc(var(--spacing) * ${String(2 + depth * 4)})` }}
            >
              <NavLink to={`/notes/${note.id}`} className={itemClass}>
                <FileText aria-hidden className="size-4 shrink-0 text-fg-muted" />
                <span className="truncate" title={note.title}>
                  {note.title}
                </span>
              </NavLink>
              <button
                type="button"
                aria-label={t("notes.newInside", { title: note.title })}
                className="grid size-6 shrink-0 place-items-center rounded-xs text-fg-muted opacity-0 group-hover:opacity-100 hover:bg-hovered focus-visible:opacity-100 [&_svg]:size-4"
                onClick={() => {
                  add(note.id);
                }}
              >
                <FilePlus2 aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
