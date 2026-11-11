// Import an exported results file (design 4.2 "Dosyadan içe aktar", 4.6 import wizard):
// pick or drop a BibTeX/RIS file, see what it holds and what is wrong with it, then log it as
// a search run of the review. Collections as a target come with Task 18.
import type { TFunction } from "i18next";
import { FileUp } from "lucide-react";
import { Dialog } from "radix-ui";
import { useEffect, useId, useState, type DragEvent, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/query";
import { fileToBase64 } from "@/lib/base64";
import { cn } from "@/lib/cn";

import {
  knownDatabases,
  usePreviewImport,
  useRunImport,
  type ImportFile,
  type ImportIssueView,
  type ImportPreview,
  type PreviewRecord,
} from "./api";

const ACCEPT = ".bib,.bibtex,.ris,.txt";
const OTHER = "other";

function today(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${String(now.getFullYear())}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  const params = error instanceof ApiError ? error.params : {};
  return t(`errors.${code}`, { ...params, defaultValue: t("errors.unknown") });
}

export function ImportDialog({
  reviewId,
  open,
  onOpenChange,
  onShowResults,
  initialPath = null,
}: {
  reviewId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onShowResults: (searchId: string) => void;
  /** A file on this computer to start with: `tez refs.bib`, "Open with TEz" (Task 22). */
  initialPath?: string | null;
}) {
  const { t } = useTranslation();
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[var(--z-dialog)] bg-fg/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[8vh] left-1/2 z-[var(--z-dialog)] flex max-h-[84vh] w-[44rem] max-w-[94vw] -translate-x-1/2 flex-col rounded-lg border border-line bg-raised shadow-popover"
        >
          <Dialog.Title className="border-b border-line px-4 py-3 text-h3">
            {t("imports.title")}
          </Dialog.Title>
          {/* Remounted on every open, so a new import starts clean. */}
          {open && (
            <ImportWizard
              reviewId={reviewId}
              initialPath={initialPath}
              onClose={() => {
                onOpenChange(false);
              }}
              onShowResults={(searchId) => {
                onOpenChange(false);
                onShowResults(searchId);
              }}
            />
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function fromPath(path: string): ImportFile {
  return { file_name: path.split(/[\\/]/).pop() ?? path, path };
}

function ImportWizard({
  reviewId,
  initialPath,
  onClose,
  onShowResults,
}: {
  reviewId: string;
  initialPath: string | null;
  onClose: () => void;
  onShowResults: (searchId: string) => void;
}) {
  const { t } = useTranslation();
  const preview = usePreviewImport();
  const run = useRunImport(reviewId);
  // A file given by path is read by the backend, which can reach this computer's disk.
  const [file, setFile] = useState<ImportFile | null>(() =>
    initialPath ? fromPath(initialPath) : null,
  );
  const [readFailed, setReadFailed] = useState(false);
  const [logRun, setLogRun] = useState(true);
  const [database, setDatabase] = useState<string>(knownDatabases[0]);
  const [otherDatabase, setOtherDatabase] = useState("");
  const [searchedAt, setSearchedAt] = useState(today);
  const [query, setQuery] = useState("");
  const [toReview, setToReview] = useState(true);
  const [toLibrary, setToLibrary] = useState(false);

  const { mutate: startPreview } = preview;
  useEffect(() => {
    if (initialPath) startPreview(fromPath(initialPath));
  }, [initialPath, startPreview]);

  async function choose(chosen: File) {
    setReadFailed(false);
    run.reset();
    try {
      const body = { file_name: chosen.name, content_base64: await fileToBase64(chosen) };
      setFile(body);
      preview.mutate(body);
    } catch {
      setReadFailed(true);
    }
  }

  const source = database === OTHER ? otherDatabase.trim() : database;
  const hasTarget = logRun || toReview || toLibrary;
  const canImport =
    file !== null &&
    preview.isSuccess &&
    preview.data.readable > 0 &&
    hasTarget &&
    (!logRun || source !== "") &&
    !run.isPending &&
    !run.isSuccess;

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    if (!canImport) return;
    run.mutate({
      ...file,
      review_id: reviewId,
      log: logRun ? { source, searched_at: searchedAt || null, query: query.trim() || null } : null,
      add_to_review: toReview,
      add_to_library: toLibrary,
      initiated_via: "gui",
    });
  }

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 space-y-4 overflow-auto p-4">
        <FilePicker fileName={file?.file_name ?? null} onChoose={(chosen) => void choose(chosen)} />
        {readFailed && (
          <p role="alert" className="text-meta text-danger">
            {t("imports.readFailed")}
          </p>
        )}
        {preview.isPending && <p className="text-meta text-fg-muted">{t("imports.reading")}</p>}
        {preview.isError && (
          <p role="alert" className="text-meta text-danger">
            {errorText(t, preview.error)}
          </p>
        )}
        {preview.isSuccess && <PreviewSummary preview={preview.data} />}

        {preview.isSuccess && preview.data.readable > 0 && (
          <fieldset className="space-y-2 rounded-md border border-line p-3">
            <legend className="px-1 text-meta text-fg-muted">{t("imports.logLegend")}</legend>
            <label className="flex items-center gap-2 text-ui">
              <input
                type="checkbox"
                className="size-4"
                checked={logRun}
                onChange={(event) => {
                  setLogRun(event.target.checked);
                }}
              />
              {t("imports.logRun")}
            </label>
            {logRun && (
              <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 pl-6">
                <span className="text-meta text-fg-muted">{t("imports.database")}</span>
                <div className="flex gap-2">
                  <select
                    aria-label={t("imports.database")}
                    className="h-8 rounded-md border border-line-strong bg-raised px-2 text-ui text-fg"
                    value={database}
                    onChange={(event) => {
                      setDatabase(event.target.value);
                    }}
                  >
                    {knownDatabases.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                    <option value={OTHER}>{t("imports.otherDatabase")}</option>
                  </select>
                  {database === OTHER && (
                    <Input
                      aria-label={t("imports.otherDatabaseName")}
                      placeholder={t("imports.otherDatabaseName")}
                      maxLength={64}
                      value={otherDatabase}
                      onChange={(event) => {
                        setOtherDatabase(event.target.value);
                      }}
                    />
                  )}
                </div>
                <label className="contents">
                  <span className="text-meta text-fg-muted">{t("imports.searchedAt")}</span>
                  <Input
                    type="date"
                    className="w-44"
                    value={searchedAt}
                    onChange={(event) => {
                      setSearchedAt(event.target.value);
                    }}
                  />
                </label>
                <label className="contents">
                  <span className="text-meta text-fg-muted">{t("imports.query")}</span>
                  <Input
                    className="font-mono"
                    placeholder={t("imports.queryPlaceholder")}
                    maxLength={4000}
                    value={query}
                    onChange={(event) => {
                      setQuery(event.target.value);
                    }}
                  />
                </label>
              </div>
            )}
            <label className="flex items-center gap-2 text-ui">
              <input
                type="checkbox"
                className="size-4"
                checked={toReview}
                onChange={(event) => {
                  setToReview(event.target.checked);
                }}
              />
              {t("imports.toReview")}
            </label>
            <label className="flex items-center gap-2 text-ui">
              <input
                type="checkbox"
                className="size-4"
                checked={toLibrary}
                onChange={(event) => {
                  setToLibrary(event.target.checked);
                }}
              />
              {t("imports.toLibrary")}
            </label>
            {!hasTarget && <p className="text-meta text-danger">{t("imports.needTarget")}</p>}
          </fieldset>
        )}

        {run.isError && (
          <p role="alert" className="text-meta text-danger">
            {errorText(t, run.error)}
          </p>
        )}
        {run.isSuccess && (
          <p role="status" className="rounded-md bg-primary-soft p-2 text-ui">
            {t("imports.done", {
              imported: run.data.imported,
              newPapers: run.data.new_papers,
              toReview: run.data.added_to_review,
            })}
          </p>
        )}
      </div>
      <footer className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
        {run.isSuccess ? (
          <>
            <Button type="button" onClick={onClose}>
              {t("imports.close")}
            </Button>
            {run.data.search_id && (
              <Button
                type="button"
                variant="primary"
                onClick={() => {
                  onShowResults(run.data.search_id ?? "");
                }}
              >
                {t("imports.showResults")}
              </Button>
            )}
          </>
        ) : (
          <>
            <Button type="button" onClick={onClose}>
              {t("imports.cancel")}
            </Button>
            <Button type="submit" variant="primary" disabled={!canImport}>
              {run.isPending
                ? t("imports.importing")
                : t("imports.import", { count: preview.data?.readable ?? 0 })}
            </Button>
          </>
        )}
      </footer>
    </form>
  );
}

function FilePicker({
  fileName,
  onChoose,
}: {
  fileName: string | null;
  onChoose: (file: File) => void;
}) {
  const { t } = useTranslation();
  const inputId = useId();
  const [over, setOver] = useState(false);

  function drop(event: DragEvent) {
    event.preventDefault();
    setOver(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped) onChoose(dropped);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => {
        setOver(false);
      }}
      onDrop={drop}
      className={cn(
        "flex items-center gap-3 rounded-md border border-dashed border-line-strong p-3",
        over && "border-primary bg-primary-soft",
      )}
    >
      <FileUp aria-hidden className="size-5 text-fg-muted" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-ui">{fileName ?? t("imports.dropHere")}</p>
        <p className="text-meta text-fg-muted">{t("imports.formats")}</p>
      </div>
      <label
        htmlFor={inputId}
        className="inline-flex h-8 cursor-pointer items-center rounded-md border border-line bg-raised px-3 text-ui font-medium hover:bg-hovered"
      >
        {t("imports.chooseFile")}
      </label>
      <input
        id={inputId}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        aria-label={t("imports.chooseFile")}
        onChange={(event) => {
          const chosen = event.target.files?.[0];
          if (chosen) onChoose(chosen);
          event.target.value = "";
        }}
      />
    </div>
  );
}

function PreviewSummary({ preview }: { preview: ImportPreview }) {
  const { t, i18n } = useTranslation();
  const number = (value: number) => value.toLocaleString(i18n.language);
  const warnings = Object.entries(preview.warnings);
  return (
    <section className="space-y-3">
      <p aria-live="polite" className="text-ui">
        {t("imports.summary", {
          format: t(`imports.formatNames.${preview.format}`),
          total: number(preview.total),
          readable: number(preview.readable),
          new: number(preview.new),
          known: number(preview.known),
          inLibrary: number(preview.in_library),
          repeated: number(preview.repeated),
        })}
      </p>
      {preview.issues.length > 0 && <IssueList issues={preview.issues} />}
      {warnings.length > 0 && (
        <p className="text-meta text-warning">
          {warnings
            .map(([warning, count]) => t(`imports.warnings.${warning}`, { count }))
            .join(" · ")}
        </p>
      )}
      {preview.sample.length > 0 && <SampleTable records={preview.sample} />}
    </section>
  );
}

function IssueList({ issues }: { issues: ImportIssueView[] }) {
  const { t } = useTranslation();
  return (
    <details open className="rounded-md border border-line p-2 text-meta">
      <summary className="cursor-pointer text-danger">
        {t("imports.issues", { count: issues.length })}
      </summary>
      <ul aria-label={t("imports.issuesLabel")} className="mt-1 max-h-40 space-y-0.5 overflow-auto">
        {issues.map((issue, index) => (
          <li key={index} className="flex gap-2">
            <span className="w-20 shrink-0 text-fg-muted">
              {issue.line !== null ? t("imports.line", { line: issue.line }) : "—"}
            </span>
            {issue.key && <span className="font-mono">{issue.key}</span>}
            <span>{t(`errors.${issue.code}`)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function SampleTable({ records }: { records: PreviewRecord[] }) {
  const { t } = useTranslation();
  return (
    <div className="overflow-auto">
      <p className="mb-1 text-meta text-fg-muted">{t("imports.sample")}</p>
      <table className="w-full text-left text-meta">
        <thead className="text-fg-muted">
          <tr className="border-b border-line">
            <th className="py-1 pr-2 font-normal">{t("imports.columns.title")}</th>
            <th className="pr-2 font-normal">{t("imports.columns.author")}</th>
            <th className="pr-2 font-normal">{t("imports.columns.year")}</th>
            <th className="pr-2 font-normal">{t("imports.columns.doi")}</th>
            <th className="font-normal">{t("imports.columns.status")}</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record, index) => {
            const flagged = (warning: string) =>
              record.warnings.includes(warning as PreviewRecord["warnings"][number]);
            return (
              <tr key={index} className="border-b border-line align-top">
                <td className="py-1 pr-2">{record.title}</td>
                <td className={cn("pr-2", flagged("no_authors") && "bg-warning/15")}>
                  {record.first_author ?? "—"}
                </td>
                <td
                  className={cn(
                    "pr-2",
                    (flagged("no_year") || flagged("bad_year")) && "bg-warning/15",
                  )}
                >
                  {record.year ?? "—"}
                </td>
                <td
                  className={cn(
                    "pr-2 font-mono break-all",
                    flagged("no_identifier") && "bg-warning/15",
                  )}
                >
                  {record.doi ?? "—"}
                </td>
                <td className="whitespace-nowrap">{t(`imports.status.${record.status}`)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
