// Right of a note (design 5.3): the notes that link to it, and what it cites.
import { BookOpen, Link2Off } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useMatch } from "react-router";

import { citationOf } from "@/features/reader/citation";

import { useBacklinks, useNote, type NoteLinkView } from "./api";
import { useOpenLink } from "./useOpenLink";

export function NotesInspector() {
  const { t } = useTranslation();
  const id = useMatch("/notes/:noteId")?.params.noteId;
  if (!id) return <p className="text-meta text-fg-muted">{t("notes.inspectorEmpty")}</p>;
  return <Links key={id} id={id} />;
}

function Links({ id }: { id: string }) {
  const { t } = useTranslation();
  const backlinks = useBacklinks(id);
  const note = useNote(id);
  const links = note.data?.links ?? [];
  const cited = new Map<string, NoteLinkView>();
  for (const link of links) {
    const key = link.target_id ?? link.label;
    if (link.target_type !== "note" && !cited.has(key)) cited.set(key, link);
  }
  const broken = links.filter((link) => link.status === "broken");
  return (
    <div className="space-y-5">
      <section aria-labelledby="note-backlinks" className="space-y-2">
        <h2 id="note-backlinks" className="text-h3">
          {t("notes.backlinks", { count: backlinks.data?.length ?? 0 })}
        </h2>
        {backlinks.data?.length === 0 && (
          <p className="text-meta text-fg-muted">{t("notes.noBacklinks")}</p>
        )}
        <ul className="space-y-2">
          {(backlinks.data ?? []).map((link) => (
            <li key={link.note_id} className="rounded-md border border-line p-2">
              <Link
                to={`/notes/${link.note_id}`}
                className="block truncate text-ui font-medium text-fg hover:underline"
              >
                {link.title}
              </Link>
              {link.passage && <p className="text-meta text-fg-muted">{link.passage}</p>}
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="note-cited" className="space-y-2">
        <h2 id="note-cited" className="text-h3">
          {t("notes.cited", { count: [...cited.values()].filter((l) => l.target_id).length })}
        </h2>
        <ul className="space-y-2">
          {[...cited.values()]
            .filter((link) => link.target_id !== null)
            .map((link) => (
              <Cited key={link.target_id} link={link} />
            ))}
        </ul>
      </section>
      {broken.length > 0 && (
        <section aria-labelledby="note-broken" className="space-y-2">
          <h2 id="note-broken" className="text-h3">
            {t("notes.broken", { count: broken.length })}
          </h2>
          <ul className="space-y-1">
            {broken.map((link, index) => (
              <li
                key={`${link.label}-${String(index)}`}
                className="flex items-center gap-1 text-meta text-danger"
              >
                <Link2Off aria-hidden className="size-3 shrink-0" />
                <span className="truncate">{link.label}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function Cited({ link }: { link: NoteLinkView }) {
  const { t } = useTranslation();
  const open = useOpenLink();
  return (
    <li className="rounded-md border border-line p-2">
      <p className="text-ui text-fg">{link.title ?? link.label}</p>
      {link.anchor?.quote && (
        <p className="line-clamp-2 font-serif text-meta text-fg-muted italic">
          {link.anchor.quote}
        </p>
      )}
      <button
        type="button"
        className="flex items-center gap-1 text-meta text-primary hover:underline"
        onClick={() => {
          void open({ type: link.target_type, id: link.target_id, label: link.label });
        }}
      >
        <BookOpen aria-hidden className="size-3" />
        {link.anchor
          ? `${citationOf(link.anchor.paper, t)} · ${t("reader.pageShort", { page: link.anchor.page })}`
          : t("notes.openPaper")}
      </button>
    </li>
  );
}
