// The reading panel, right of the document (design 4.5): its highlights with their comments.
import { Copy, MapPinOff, NotebookPen, Search, SquareDashed, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useMatch } from "react-router";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { PaperCells } from "@/features/matrix/PaperCells";
import { cn } from "@/lib/cn";
import { fold } from "@/lib/text";

import {
  highlightColors,
  highlightVar,
  useAnnotations,
  useCreateAnnotation,
  useDeleteAnnotation,
  useUpdateAnnotation,
  type AnnotationView,
} from "./api";
import { quoteWithSource } from "./quote";
import { PaperNotes } from "./PaperNotes";
import { QuoteToNote } from "./QuoteToNote";
import { useReaderSelection, useReadingPanel } from "./store";

export function ReaderInspector() {
  const { t } = useTranslation();
  const attachmentId = useMatch("/reader/:attachmentId")?.params.attachmentId;
  const { tab, setTab } = useReadingPanel();
  if (!attachmentId) {
    return <p className="text-meta text-fg-muted">{t("reader.highlights.noDocument")}</p>;
  }
  return (
    <div className="space-y-3">
      <Segmented
        aria-label={t("reader.panelTabs")}
        value={tab}
        options={[
          { value: "highlights", label: t("reader.highlights.tab") },
          { value: "notes", label: t("reader.notes.tab") },
          { value: "matrix", label: t("matrix.reader.tab") },
        ]}
        onValueChange={setTab}
      />
      {tab === "highlights" ? (
        <Highlights key={attachmentId} attachmentId={attachmentId} />
      ) : tab === "notes" ? (
        <PaperNotes key={attachmentId} attachmentId={attachmentId} />
      ) : (
        <PaperCells key={attachmentId} attachmentId={attachmentId} />
      )}
    </div>
  );
}

function Highlights({ attachmentId }: { attachmentId: string }) {
  const { t } = useTranslation();
  const annotations = useAnnotations(attachmentId);
  const remove = useDeleteAnnotation(attachmentId);
  const restore = useCreateAnnotation(attachmentId);
  const [filter, setFilter] = useState("");
  const [deleted, setDeleted] = useState<AnnotationView | null>(null);
  const wanted = fold(filter.trim());
  const shown = (annotations.data ?? []).filter(
    (a) => wanted === "" || fold(`${a.anchor.quote} ${a.comment}`).includes(wanted),
  );

  return (
    <section aria-labelledby="reader-highlights" className="space-y-3">
      <h2 id="reader-highlights" className="text-h3">
        {t("reader.highlights.title", { count: annotations.data?.length ?? 0 })}
      </h2>
      {(annotations.data?.length ?? 0) > 0 && (
        <div className="relative">
          <Search
            aria-hidden
            className="pointer-events-none absolute top-1/2 left-2 size-4 -translate-y-1/2 text-fg-muted"
          />
          <Input
            type="search"
            className="pl-8"
            aria-label={t("reader.highlights.search")}
            placeholder={t("reader.highlights.search")}
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value);
            }}
          />
        </div>
      )}
      {deleted && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-md border border-line bg-surface px-2 py-1 text-meta"
        >
          <span className="flex-1">{t("reader.highlights.deleted")}</span>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              const { anchor, color, comment } = deleted;
              restore.mutate({
                anchor: {
                  kind: anchor.kind,
                  page: anchor.page,
                  rects: anchor.rects,
                  quote: anchor.quote,
                  prefix: anchor.prefix,
                  suffix: anchor.suffix,
                },
                color,
                comment,
              });
              setDeleted(null);
            }}
          >
            {t("reader.highlights.undo")}
          </Button>
        </p>
      )}
      {annotations.isSuccess && annotations.data.length === 0 && !deleted && (
        <p className="text-meta text-fg-muted">{t("reader.highlights.empty")}</p>
      )}
      {wanted !== "" && shown.length === 0 && (
        <p className="text-meta text-fg-muted">{t("reader.highlights.none")}</p>
      )}
      <ul className="space-y-2">
        {shown.map((annotation) => (
          <Highlight
            key={annotation.id}
            annotation={annotation}
            attachmentId={attachmentId}
            onDelete={() => {
              remove.mutate(annotation.id, {
                onSuccess: () => {
                  setDeleted(annotation);
                },
              });
            }}
          />
        ))}
      </ul>
    </section>
  );
}

function Highlight({
  annotation,
  attachmentId,
  onDelete,
}: {
  annotation: AnnotationView;
  attachmentId: string;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const { selectedId, editing, select } = useReaderSelection();
  const selected = annotation.id === selectedId;
  const item = useRef<HTMLLIElement>(null);
  const { anchor } = annotation;
  const lost = anchor.status === "lost" || anchor.status === "checking";
  const update = useUpdateAnnotation(attachmentId);
  const [quoting, setQuoting] = useState(false);
  useEffect(() => {
    if (selected) item.current?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  return (
    <li
      ref={item}
      aria-current={selected ? "true" : undefined}
      className={cn(
        "space-y-2 rounded-md border bg-raised p-2",
        selected ? "border-primary ring-1 ring-primary" : "border-line",
      )}
    >
      <div className="flex items-center gap-1">
        <Link
          to={`/reader/${attachmentId}?anchor=${anchor.id}`}
          className="rounded-xs bg-primary-soft px-1.5 font-mono text-meta text-primary hover:underline"
          onClick={() => {
            select(annotation.id);
          }}
        >
          {t("reader.pageShort", { page: anchor.page })}
        </Link>
        {annotation.kind === "area" && (
          <SquareDashed aria-label={t("reader.highlights.area")} className="size-4 text-fg-muted" />
        )}
        <div className="flex-1" />
        {highlightColors.map((color) => (
          <button
            key={color}
            type="button"
            aria-label={t(`reader.selection.highlight.${color}`)}
            aria-pressed={color === annotation.color}
            className="grid size-5 place-items-center rounded-full hover:bg-hovered"
            onClick={() => {
              update.mutate({ id: annotation.id, color });
            }}
          >
            <span
              aria-hidden
              className={cn("size-3 rounded-full", color === annotation.color && "ring-2 ring-fg")}
              style={{ backgroundColor: highlightVar(color) }}
            />
          </button>
        ))}
        <Button
          variant="ghost"
          size="icon"
          className="size-6"
          aria-label={t("reader.quote.action")}
          onClick={() => {
            setQuoting(true);
          }}
        >
          <NotebookPen />
        </Button>
        {anchor.quote && (
          <Button
            variant="ghost"
            size="icon"
            className="size-6"
            aria-label={t("reader.highlights.copy")}
            onClick={() => {
              void navigator.clipboard.writeText(quoteWithSource(anchor, t));
            }}
          >
            <Copy />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="size-6"
          aria-label={t("reader.highlights.delete")}
          onClick={onDelete}
        >
          <Trash2 />
        </Button>
      </div>
      {anchor.quote && (
        <blockquote
          className="border-l-2 pl-2 font-serif text-ui text-fg italic"
          style={{ borderColor: highlightVar(annotation.color) }}
        >
          {anchor.quote}
        </blockquote>
      )}
      {lost && (
        <p className="flex items-center gap-1 text-meta text-danger">
          <MapPinOff aria-hidden className="size-3" />
          {t(anchor.status === "lost" ? "reader.highlights.lost" : "reader.highlights.checking")}
        </p>
      )}
      {quoting && (
        <QuoteToNote
          anchor={anchor}
          onDone={() => {
            setQuoting(false);
          }}
          onCancel={() => {
            setQuoting(false);
          }}
        />
      )}
      <Comment
        // The saved comment is the editor's starting point.
        key={annotation.comment}
        annotation={annotation}
        autoFocus={selected && editing}
        onSave={(comment) => {
          update.mutate({ id: annotation.id, comment });
        }}
      />
    </li>
  );
}

function Comment({
  annotation,
  autoFocus,
  onSave,
}: {
  annotation: AnnotationView;
  autoFocus: boolean;
  onSave: (comment: string) => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState(annotation.comment);
  const field = useRef<HTMLTextAreaElement>(null);
  const endEditing = useReaderSelection((state) => state.endEditing);
  useEffect(() => {
    if (!autoFocus) return;
    field.current?.focus();
    endEditing();
  }, [autoFocus, endEditing]);
  const save = () => {
    if (text.trim() !== annotation.comment) onSave(text);
  };
  return (
    <textarea
      ref={field}
      rows={text === "" ? 1 : Math.min(6, text.split("\n").length + 1)}
      className="w-full resize-y rounded-md border border-transparent bg-transparent px-1 py-0.5 text-ui text-fg placeholder:text-fg-muted hover:border-line focus:border-line focus:bg-canvas"
      aria-label={t("reader.highlights.comment")}
      placeholder={t("reader.highlights.commentPlaceholder")}
      value={text}
      onChange={(event) => {
        setText(event.target.value);
      }}
      onBlur={save}
      onKeyDown={(event) => {
        if (event.key === "Escape") event.currentTarget.blur();
        if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) event.currentTarget.blur();
      }}
    />
  );
}
