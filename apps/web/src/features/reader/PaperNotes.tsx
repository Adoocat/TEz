// The reading panel's "Notes" tab: notes about the paper being read.
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { useAttachment } from "@/features/files/api";
import { usePaperDetail } from "@/features/library/api";
import { useCreateNote, usePaperNotes } from "@/features/notes/api";

export function PaperNotes({ attachmentId }: { attachmentId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const paperId = useAttachment(attachmentId).data?.paper_id ?? null;
  const paper = usePaperDetail(paperId);
  const notes = usePaperNotes(paperId);
  const create = useCreateNote();
  return (
    <section aria-label={t("reader.notes.title")} className="space-y-3">
      <Button
        size="sm"
        disabled={paperId === null || create.isPending}
        onClick={() => {
          create.mutate(
            { title: paper.data?.title ?? t("notes.untitled"), paper_id: paperId },
            { onSuccess: (note) => void navigate(`/notes/${note.id}`) },
          );
        }}
      >
        <Plus aria-hidden />
        {t("reader.notes.new")}
      </Button>
      {notes.data?.length === 0 && (
        <p className="text-meta text-fg-muted">{t("reader.notes.none")}</p>
      )}
      <ul className="space-y-2">
        {(notes.data ?? []).map((note) => (
          <li key={note.note_id} className="rounded-md border border-line p-2">
            <Link
              to={`/notes/${note.note_id}`}
              className="block truncate text-ui font-medium text-fg hover:underline"
            >
              {note.title}
            </Link>
            {note.passage && <p className="text-meta text-fg-muted">{note.passage}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
