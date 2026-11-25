// "Quote in a note" (design 4.5): which note the passage goes to. Notes about the paper come
// first; a new one about it is always offered.
import { FilePlus2, FileText } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAppendToNote, useCreateNote, useNotes, usePaperNotes } from "@/features/notes/api";
import { ApiError } from "@/lib/api/query";
import { fold } from "@/lib/text";

import type { AnchorView } from "./api";
import { quoteBlock } from "./quote";

const SHOWN = 8;

export interface QuotedIn {
  id: string;
  title: string;
}

/** Puts passages into notes. `into` adds to a note that is already known. */
export function useQuote() {
  const { t } = useTranslation();
  const append = useAppendToNote();
  const create = useCreateNote();
  return {
    error: append.error ?? create.error,
    isPending: append.isPending || create.isPending,
    into: async (anchor: AnchorView, noteId: string): Promise<QuotedIn> =>
      append.mutateAsync({ id: noteId, text: quoteBlock(anchor, t) }),
    intoNew: async (anchor: AnchorView): Promise<QuotedIn> =>
      create.mutateAsync({
        title: anchor.paper.title,
        paper_id: anchor.paper.id,
        body: `${quoteBlock(anchor, t)}\n`,
      }),
  };
}

export function QuoteToNote({
  anchor,
  onDone,
  onCancel,
}: {
  anchor: AnchorView;
  onDone: (note: QuotedIn) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const quote = useQuote();
  const about = usePaperNotes(anchor.paper.id);
  const all = useNotes();
  const [filter, setFilter] = useState("");
  const first = new Set((about.data ?? []).map((note) => note.note_id));
  const wanted = fold(filter.trim());
  const notes = [
    ...(all.data ?? []).filter((note) => first.has(note.id)),
    ...(all.data ?? []).filter((note) => !first.has(note.id)),
  ].filter((note) => wanted === "" || fold(note.title).includes(wanted));
  const shown = notes.slice(0, SHOWN);

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-1/4 left-1/2 z-[var(--z-dialog)] w-112 max-w-[90vw] -translate-x-1/2 space-y-3 rounded-lg border border-line bg-raised p-4 shadow-popover"
        >
          <Dialog.Title className="text-h3">{t("reader.quote.title")}</Dialog.Title>
          {anchor.quote && (
            <blockquote className="line-clamp-3 border-l-2 border-line-strong pl-2 font-serif text-ui text-fg-muted italic">
              {anchor.quote}
            </blockquote>
          )}
          <Input
            type="search"
            aria-label={t("reader.quote.filter")}
            placeholder={t("reader.quote.filter")}
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value);
            }}
          />
          <ul aria-label={t("reader.quote.notes")} className="space-y-1">
            <li>
              <Button
                variant="ghost"
                className="w-full justify-start"
                disabled={quote.isPending}
                onClick={() => {
                  void quote.intoNew(anchor).then(onDone);
                }}
              >
                <FilePlus2 aria-hidden />
                <span className="truncate">{t("reader.quote.newNote")}</span>
              </Button>
            </li>
            {shown.map((note) => (
              <li key={note.id}>
                <Button
                  variant="ghost"
                  className="w-full justify-start"
                  disabled={quote.isPending}
                  onClick={() => {
                    void quote.into(anchor, note.id).then(onDone);
                  }}
                >
                  <FileText aria-hidden />
                  <span className="truncate">{note.title}</span>
                  {first.has(note.id) && (
                    <span className="ml-auto shrink-0 text-meta text-fg-muted">
                      {t("reader.quote.about")}
                    </span>
                  )}
                </Button>
              </li>
            ))}
          </ul>
          {notes.length > shown.length && (
            <p className="text-meta text-fg-muted">
              {t("reader.quote.more", { count: notes.length - shown.length })}
            </p>
          )}
          {quote.error && (
            <p role="alert" className="text-meta text-danger">
              {t(`errors.${quote.error instanceof ApiError ? quote.error.code : "unknown"}`, {
                defaultValue: t("errors.unknown"),
              })}
            </p>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
