// The paper inspector for the library (design 4.4): warnings, title and citation, quick
// actions (reading status, tags), identifiers, the editable citation key, and tabs for the
// abstract and the files.
import { BookOpen, Check, Copy, Pencil } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { ApiError } from "@/lib/api/query";

import {
  readingStatuses,
  useCollections,
  usePaperDetail,
  useSetReadingStatus,
  useTagPapers,
  useTags,
  useUpdateCitekey,
  type PaperDetail,
} from "./api";
import { PdfIcon } from "./PaperTable";
import { publicationTypeOf } from "./publicationType";
import { useLibraryView } from "./store";
import { tagColorVar } from "./tagColor";

type Tab = "abstract" | "files";

export function LibraryInspector() {
  const { t } = useTranslation();
  const { selectedPaperId } = useLibraryView();
  const detail = usePaperDetail(selectedPaperId);

  if (selectedPaperId === null) {
    return <p className="text-meta text-fg-muted">{t("library.inspectorEmpty")}</p>;
  }
  if (!detail.data) return null;
  // Remount per paper: edits in progress belong to the paper they started on.
  return <PaperInspector key={detail.data.id} paper={detail.data} />;
}

function PaperInspector({ paper }: { paper: PaperDetail }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("abstract");
  const authors = paper.authors.map((a) => a.display_name).join(", ");
  const type = publicationTypeOf(paper);
  const typeLabel = type && t(`search.venueTypes.${type}`);
  const published = paper.related.find((r) => r.relation === "published_version");
  const navigate = useNavigate();
  // A readable file first; a broken one can still be tried.
  const pdf =
    paper.attachments.find((a) => a.kind === "pdf" && a.text_status !== "failed") ??
    paper.attachments[0];

  return (
    <div className="space-y-4">
      {paper.retraction_status !== "none" && (
        <p role="alert" className="rounded-md border border-danger p-2 text-meta text-danger">
          {t(`library.retraction.${paper.retraction_status}`)}
        </p>
      )}
      {published && (
        <p className="rounded-md bg-primary-soft p-2 text-meta">
          {t("library.hasPublishedVersion", { title: published.title, year: published.year ?? "" })}
        </p>
      )}
      <div className="space-y-1">
        <h2 className="font-serif text-h3">{paper.title}</h2>
        {authors && <p className="text-meta">{authors}</p>}
        <p className="text-meta text-fg-muted">
          {[
            typeLabel,
            paper.venue,
            paper.year,
            paper.volume && `${paper.volume}(${paper.issue ?? ""})`,
            paper.pages,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      </div>
      {pdf && (
        <Button
          variant="primary"
          className="w-full"
          onClick={() => {
            void navigate(`/reader/${pdf.id}`);
          }}
        >
          <BookOpen aria-hidden />
          {t("library.openPdf")}
        </Button>
      )}
      <QuickActions paper={paper} />
      <dl className="space-y-1 text-meta">
        {Object.entries(paper.identifiers).map(([scheme, value]) => (
          <IdentifierRow key={scheme} label={scheme.toUpperCase()} value={value} />
        ))}
      </dl>
      <CitekeyEditor paper={paper} />
      <Segmented
        aria-label={t("library.inspectorTabs")}
        value={tab}
        onValueChange={setTab}
        options={[
          { value: "abstract", label: t("library.tabAbstract") },
          { value: "files", label: t("library.tabFiles", { count: paper.attachments.length }) },
        ]}
      />
      {tab === "abstract" ? (
        <p className="font-serif text-ui leading-relaxed">
          {paper.abstract ?? <span className="text-fg-muted">{t("library.noAbstract")}</span>}
        </p>
      ) : (
        <Files paper={paper} />
      )}
    </div>
  );
}

function QuickActions({ paper }: { paper: PaperDetail }) {
  const { t } = useTranslation();
  const reading = useSetReadingStatus();
  const tags = useTags();
  const tag = useTagPapers();
  const collections = useCollections();
  const mine = (tags.data ?? []).filter((item) => paper.tag_ids.includes(item.id));
  const others = (tags.data ?? []).filter((item) => !paper.tag_ids.includes(item.id));
  const inCollections = (collections.data ?? []).filter((c) => paper.collection_ids.includes(c.id));
  const selectClass = "h-7 rounded-md border border-line bg-raised px-1 text-meta text-fg";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label={t("library.readingStatus")}
          className={selectClass}
          value={paper.reading_status}
          onChange={(event) => {
            const status = readingStatuses.find((value) => value === event.target.value);
            if (status) reading.mutate({ paper_ids: [paper.id], reading_status: status });
          }}
        >
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
          disabled={others.length === 0}
          onChange={(event) => {
            if (event.target.value) tag.mutate({ id: event.target.value, paperIds: [paper.id] });
          }}
        >
          <option value="">{t("library.addTag")}</option>
          {others.map((item) => (
            <option key={item.id} value={item.id}>
              #{item.name}
            </option>
          ))}
        </select>
      </div>
      {mine.length > 0 && (
        <ul aria-label={t("library.tags")} className="flex flex-wrap gap-1">
          {mine.map((item) => (
            <li
              key={item.id}
              className="flex items-center gap-1 rounded-xs border border-line px-1.5 text-meta"
            >
              <span
                aria-hidden
                className="size-2 rounded-full"
                style={{ backgroundColor: tagColorVar(item.color) }}
              />
              #{item.name}
              <button
                type="button"
                className="text-fg-muted hover:text-fg"
                aria-label={t("library.removeTag", { name: item.name })}
                onClick={() => {
                  tag.mutate({ id: item.id, paperIds: [paper.id], remove: true });
                }}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      {inCollections.length > 0 && (
        <p className="text-meta text-fg-muted">
          {t("library.inCollections")}{" "}
          {inCollections.map((c) => (c.is_system ? t("library.inbox") : c.name)).join(", ")}
        </p>
      )}
    </div>
  );
}

function IdentifierRow({ label, value }: { label: string; value: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-2">
      <dt className="w-14 shrink-0 text-fg-muted">{label}</dt>
      <dd className="min-w-0 flex-1 truncate font-mono">{value}</dd>
      <Button
        variant="ghost"
        size="icon"
        className="size-6 [&_svg]:size-3.5"
        aria-label={t("library.copyNamed", { name: label })}
        onClick={() => {
          void navigator.clipboard.writeText(value).then(() => {
            setCopied(true);
          });
        }}
      >
        {copied ? <Check /> : <Copy />}
      </Button>
    </div>
  );
}

function CitekeyEditor({ paper }: { paper: PaperDetail }) {
  const { t } = useTranslation();
  const update = useUpdateCitekey();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(paper.citekey ?? "");

  if (!editing) {
    return (
      <div className="flex items-center gap-2 text-meta">
        <span className="w-14 shrink-0 text-fg-muted">{t("library.citekey")}</span>
        <span className="min-w-0 flex-1 truncate font-mono">{paper.citekey ?? "—"}</span>
        <Button
          variant="ghost"
          size="icon"
          className="size-6 [&_svg]:size-3.5"
          aria-label={t("library.editCitekey")}
          onClick={() => {
            setEditing(true);
          }}
        >
          <Pencil />
        </Button>
      </div>
    );
  }
  const error = update.error;
  return (
    <form
      className="space-y-1"
      onSubmit={(event) => {
        event.preventDefault();
        if (!value.trim()) return;
        update.mutate(
          { id: paper.id, citekey: value.trim() },
          {
            onSuccess: () => {
              setEditing(false);
            },
          },
        );
      }}
    >
      <Input
        autoFocus
        aria-label={t("library.citekey")}
        className="h-7 font-mono"
        maxLength={128}
        value={value}
        onChange={(event) => {
          setValue(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") setEditing(false);
        }}
      />
      {error && (
        <p role="alert" className="text-meta text-danger">
          {t(`errors.${error instanceof ApiError ? error.code : "unknown"}`, {
            ...(error instanceof ApiError ? error.params : {}),
            defaultValue: t("errors.unknown"),
          })}
        </p>
      )}
    </form>
  );
}

function Files({ paper }: { paper: PaperDetail }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  if (paper.attachments.length === 0) {
    return <p className="text-meta text-fg-muted">{t("library.noFiles")}</p>;
  }
  return (
    <ul className="space-y-2">
      {paper.attachments.map((file) => (
        <li key={file.id} className="flex items-start gap-2 text-meta">
          <PdfIcon state={file.text_status} />
          <div className="min-w-0 flex-1">
            <button
              type="button"
              className="max-w-full truncate text-left text-primary hover:underline"
              aria-label={t("library.openNamed", {
                name: file.file_name ?? file.sha256.slice(0, 12),
              })}
              onClick={() => {
                void navigate(`/reader/${file.id}`);
              }}
            >
              {file.file_name ?? file.sha256.slice(0, 12)}
            </button>
            <p className="text-fg-muted">
              {[
                file.page_count !== null && t("library.pages", { count: file.page_count }),
                file.size !== null &&
                  t("library.megabytes", {
                    size: (file.size / 1024 / 1024).toLocaleString(i18n.language, {
                      maximumFractionDigits: 1,
                    }),
                  }),
                t(`library.pdf.${file.text_status}`),
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            {file.error && (
              <p className="text-danger">
                {t(`errors.${file.error.code}`, {
                  ...file.error.params,
                  defaultValue: t("errors.unknown"),
                })}
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
