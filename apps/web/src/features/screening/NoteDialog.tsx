// A short screening note on the record (N). Screening keys stay quiet while it is open.
import { Dialog } from "radix-ui";
import { useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

export function NoteDialog({
  open,
  initial,
  onSave,
  onClose,
}: {
  open: boolean;
  initial: string;
  onSave: (note: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content className="fixed top-1/4 left-1/2 z-[var(--z-dialog)] w-[32rem] max-w-[90vw] -translate-x-1/2 rounded-lg border border-line bg-raised p-4 shadow-popover">
          <Dialog.Title className="text-h3">{t("screening.note.title")}</Dialog.Title>
          <Dialog.Description className="mt-1 text-meta text-fg-muted">
            {t("screening.note.hint")}
          </Dialog.Description>
          {/* Mounted only while open, so it starts from the record's current note. */}
          {open && <NoteForm initial={initial} onSave={onSave} onClose={onClose} />}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function NoteForm({
  initial,
  onSave,
  onClose,
}: {
  initial: string;
  onSave: (note: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [note, setNote] = useState(initial);

  function save(event: SyntheticEvent) {
    event.preventDefault();
    onSave(note.trim());
  }

  return (
    <form onSubmit={save} className="mt-3 space-y-3">
      <textarea
        aria-label={t("screening.note.title")}
        className="h-32 w-full rounded-md border border-line-strong bg-raised p-2 text-ui"
        maxLength={10000}
        value={note}
        onChange={(event) => {
          setNote(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) save(event);
        }}
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>
          {t("screening.note.cancel")}
        </Button>
        <Button type="submit" variant="primary">
          {t("screening.note.save")}
        </Button>
      </div>
    </form>
  );
}
