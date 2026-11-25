// The notes screen (design 5.3): the note being written, side by side with how it reads. Loaded
// when first opened: the editor is not part of the start-up bundle.
import { AlertTriangle, Check, CloudOff, NotebookPen, Pencil, Trash2 } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router";

import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { ApiError } from "@/lib/api/query";
import { cn } from "@/lib/cn";

import {
  useCreateNote,
  useDeleteNote,
  useLinkSuggestions,
  useNote,
  useNotes,
  useRestoreNote,
  type NoteView,
} from "./api";
import { MarkdownEditor } from "./MarkdownEditor";
import { MarkdownPreview } from "./MarkdownPreview";
import { useNoteMode } from "./store";
import { possibleParents, treeOf } from "./tree";
import { useNoteDraft, type SaveState } from "./useNoteDraft";
import { useOpenLink } from "./useOpenLink";

export function NotesPage() {
  const { t } = useTranslation();
  const { noteId } = useParams();
  if (noteId) return <OpenNote key={noteId} id={noteId} />;
  return (
    <div className="grid h-full place-items-center p-6 text-center">
      <div className="max-w-sm space-y-2">
        <NotebookPen aria-hidden className="mx-auto size-6 text-fg-muted" />
        <h1 className="text-h2">{t("nav.notes")}</h1>
        <p className="text-ui text-fg-muted">{t("notes.nothingOpen")}</p>
      </div>
    </div>
  );
}

function OpenNote({ id }: { id: string }) {
  const { t } = useTranslation();
  const note = useNote(id);
  const restore = useRestoreNote();
  // Counts reloads: the editor starts again from the saved text.
  const [round, setRound] = useState(0);
  const [deleted, setDeleted] = useState(false);

  if (deleted || (note.error instanceof ApiError && note.error.code === "note.not_found")) {
    return (
      <div role="alert" className="space-y-2 p-6 text-ui text-fg-muted">
        <p>{t("notes.deleted")}</p>
        <Button
          size="sm"
          onClick={() => {
            restore.mutate(id, {
              onSuccess: () => {
                setDeleted(false);
                void note.refetch();
              },
            });
          }}
        >
          {t("notes.restore")}
        </Button>
      </div>
    );
  }
  if (!note.data) return null;
  return (
    <NoteEditor
      key={round}
      note={note.data}
      onReload={() => {
        void note.refetch().then(() => {
          setRound((n) => n + 1);
        });
      }}
      onDeleted={() => {
        setDeleted(true);
      }}
    />
  );
}

function NoteEditor({
  note,
  onReload,
  onDeleted,
}: {
  note: NoteView;
  onReload: () => void;
  onDeleted: () => void;
}) {
  const { t, i18n } = useTranslation();
  const draft = useNoteDraft(note);
  const { mode, setMode } = useNoteMode();
  const notes = useNotes();
  const remove = useDeleteNote();
  const create = useCreateNote();
  const suggest = useLinkSuggestions();
  const open = useOpenLink(note.links);
  // The preview may lag behind fast typing; the editor may not.
  const shown = useDeferredValue(draft.body);
  const words = draft.body.split(/\s+/).filter(Boolean).length;
  const parents = possibleParents(notes.data ?? [], note.id);
  const current = notes.data?.find((n) => n.id === note.id);
  const depths = new Map(treeOf(parents, i18n.language).map((item) => [item.note.id, item.depth]));

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-1.5">
        <input
          aria-label={t("notes.title")}
          className="min-w-40 flex-1 rounded-md border border-transparent bg-transparent px-1 text-h3 text-fg hover:border-line focus:border-line"
          value={draft.title}
          placeholder={t("notes.untitled")}
          onChange={(event) => {
            draft.setTitle(event.target.value);
          }}
        />
        <SaveStatus state={draft.state} onRetry={draft.retry} />
        <span className="text-meta text-fg-muted tabular-nums">
          {t("notes.words", { count: words, n: words.toLocaleString(i18n.language) })}
        </span>
        <select
          aria-label={t("notes.place")}
          className="h-7 max-w-40 rounded-md border border-line bg-raised px-1 text-meta text-fg"
          value={current?.parent_id ?? ""}
          onChange={(event) => {
            void draft.moveTo(event.target.value || null);
          }}
        >
          <option value="">{t("notes.topLevel")}</option>
          {treeOf(parents, i18n.language).map(({ note: parent }) => (
            <option key={parent.id} value={parent.id}>
              {`${"  ".repeat(depths.get(parent.id) ?? 0)}${parent.title}`}
            </option>
          ))}
        </select>
        <Segmented
          aria-label={t("notes.view")}
          value={mode}
          options={[
            { value: "edit", label: t("notes.edit") },
            { value: "both", label: t("notes.both") },
            { value: "preview", label: t("notes.preview") },
          ]}
          onValueChange={setMode}
        />
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("notes.delete")}
          onClick={() => {
            draft.dropMine();
            remove.mutate(note.id, {
              onSuccess: () => {
                onDeleted();
              },
            });
          }}
        >
          <Trash2 />
        </Button>
      </header>
      {draft.state === "conflict" && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-2 border-b border-line bg-surface px-4 py-1.5 text-meta"
        >
          <AlertTriangle aria-hidden className="size-4 text-danger" />
          <span className="flex-1">{t(draft.left ? "notes.draftLeft" : "notes.conflict")}</span>
          <Button
            size="sm"
            onClick={() => {
              void draft.keepMine().then(onReload);
            }}
          >
            {t("notes.keepMine")}
          </Button>
          <Button
            size="sm"
            onClick={() => {
              draft.dropMine();
              onReload();
            }}
          >
            {t("notes.useSaved")}
          </Button>
        </div>
      )}
      <div className="flex min-h-0 flex-1">
        {mode !== "preview" && (
          <div className={cn("min-w-0 flex-1", mode === "both" && "border-r border-line")}>
            <MarkdownEditor
              initial={draft.body}
              label={t("notes.body")}
              placeholder={t("notes.placeholder")}
              newNoteLabel={(title) => t("notes.newNamed", { title })}
              links={note.links}
              onChange={draft.setBody}
              onOpenLink={(link) => void open(link)}
              suggest={suggest}
              createNote={async (title) =>
                (await create.mutateAsync({ title, parent_id: note.parent_id })).id
              }
            />
          </div>
        )}
        {mode !== "edit" && (
          <article
            aria-label={t("notes.preview")}
            className="min-w-0 flex-1 overflow-auto px-6 py-4"
          >
            <h1 className="mb-3 text-h1">{draft.title}</h1>
            <MarkdownPreview
              text={shown}
              links={note.links}
              onOpenLink={(link) => void open(link)}
            />
          </article>
        )}
      </div>
    </div>
  );
}

function SaveStatus({ state, onRetry }: { state: SaveState; onRetry: () => void }) {
  const { t } = useTranslation();
  if (state === "failed") {
    return (
      <span role="alert" className="flex items-center gap-1 text-meta text-danger">
        <CloudOff aria-hidden className="size-4" />
        {t("notes.saveFailed")}
        <Button size="sm" variant="ghost" onClick={onRetry}>
          {t("notes.retry")}
        </Button>
      </span>
    );
  }
  return (
    <span role="status" className="flex items-center gap-1 text-meta text-fg-muted">
      {state === "saved" ? (
        <Check aria-hidden className="size-4" />
      ) : (
        <Pencil aria-hidden className="size-4" />
      )}
      {t(`notes.state.${state}`)}
    </span>
  );
}
