// The export screen (design 5.10, Task 40): pick the papers (a review's included studies,
// papers chosen in the library, a collection or the whole library) and a format (a formatted
// bibliography, BibTeX or RIS); copy or save it; copy the `tez export` command that does the
// same; and the search strategy table for the methods chapter.
import type { TFunction } from "i18next";
import { Clipboard, Download, Terminal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { useBackend } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { useCollections } from "@/features/library/api";
import { useActiveReview } from "@/features/reviews/store";
import { ApiError } from "@/lib/api/query";

import {
  useBibliography,
  useReferences,
  useSearchStrategy,
  type CslLocale,
  type CslStyle,
  type ScopeRequest,
  type StrategyRow,
} from "./api";
import { exportCommand, type CommandScope } from "./command";
import { InlineHtml } from "./InlineHtml";
import { useExportChoices, useExportSelection, type ExportFormat, type ScopeKind } from "./store";
import { localDate, strategyCsv, strategyMarkdown, type StrategyLabels } from "./strategy";

/** In the order most theses use them. */
const styles: CslStyle[] = [
  "apa",
  "mla",
  "chicago-author-date",
  "chicago-notes",
  "vancouver",
  "ieee",
];
const PREVIEW_ENTRIES = 5;
const PREVIEW_LINES = 60;
const BYTE_ORDER_MARK = "\u{FEFF}";

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  return t(`errors.${code}`, { defaultValue: t("errors.unknown") });
}

/** A short-lived note after copying or saving, read out by screen readers. */
function useNotice(): [string | null, (text: string) => void] {
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (notice === null) return;
    const timer = setTimeout(() => {
      setNotice(null);
    }, 2500);
    return () => {
      clearTimeout(timer);
    };
  }, [notice]);
  return [notice, setNotice];
}

export function ExportPage() {
  const { t, i18n } = useTranslation();
  const { platform } = useBackend();
  const review = useActiveReview();
  const collections = useCollections();
  const chosen = useExportSelection((state) => state.paperIds);
  const choices = useExportChoices();
  const [scope, setScope] = useState<ScopeKind>(() =>
    chosen.length > 0 ? "selected" : "included",
  );
  const [collectionId, setCollectionId] = useState<string>("");
  const [notice, setNotice] = useNotice();

  const userCollections = (collections.data ?? []).filter((c) => !c.is_system);
  const collection = userCollections.find((c) => c.id === collectionId) ?? userCollections[0];
  const effectiveScope: ScopeKind =
    scope === "included" && !review
      ? "library"
      : scope === "selected" && chosen.length === 0
        ? "library"
        : scope === "collection" && !collection
          ? "library"
          : scope;
  const reviewId = review?.id;
  const chosenCollectionId = collection?.id;
  const request: ScopeRequest =
    effectiveScope === "included" && reviewId
      ? { review_id: reviewId, included: true }
      : effectiveScope === "selected"
        ? { paper_ids: chosen }
        : effectiveScope === "collection" && chosenCollectionId
          ? { collection_id: chosenCollectionId }
          : {};

  const locale: CslLocale = choices.locale ?? (i18n.language.startsWith("tr") ? "tr-TR" : "en-US");
  const isBibliography = choices.format === "bibliography";
  const referenceFormat = choices.format === "ris" ? "ris" : "bibtex";
  const bibliography = useBibliography(choices.style, locale, request, isBibliography);
  const references = useReferences(referenceFormat, request, !isBibliography);
  const result = isBibliography ? bibliography : references;
  const count = result.data?.count;

  const run = (work: Promise<void>, done: string) => {
    work.then(
      () => {
        setNotice(done);
      },
      () => {
        setNotice(t("export.failed"));
      },
    );
  };
  const fileName = isBibliography
    ? `bibliography-${choices.style}.html`
    : referenceFormat === "ris"
      ? "references.ris"
      : "references.bib";
  const copy = () => {
    if (bibliography.data && isBibliography) {
      run(platform.copyText(bibliography.data.text, bibliography.data.html), t("export.copied"));
    } else if (references.data && !isBibliography) {
      run(platform.copyText(references.data.content), t("export.copied"));
    }
  };
  const save = () => {
    if (bibliography.data && isBibliography) {
      const page = `<!doctype html>\n<html><head><meta charset="utf-8"><title>${t("export.bibliographyTitle")}</title></head><body>\n${bibliography.data.html}\n</body></html>\n`;
      run(platform.saveFile(fileName, page, "text/html"), t("export.saved", { fileName }));
    } else if (references.data && !isBibliography) {
      const mime =
        referenceFormat === "ris" ? "application/x-research-info-systems" : "application/x-bibtex";
      run(
        platform.saveFile(fileName, references.data.content, mime),
        t("export.saved", { fileName }),
      );
    }
  };

  const commandScope: CommandScope | null =
    effectiveScope === "included" && review
      ? { kind: "review", title: review.title, included: true }
      : effectiveScope === "collection" && collection
        ? { kind: "collection", name: collection.name }
        : effectiveScope === "library"
          ? { kind: "library" }
          : null;
  const command =
    !isBibliography && commandScope ? exportCommand(referenceFormat, commandScope, fileName) : null;

  const scopeOptions: {
    kind: ScopeKind;
    label: string;
    hint?: string | undefined;
    disabled: boolean;
  }[] = [
    {
      kind: "included",
      label: t("export.scope.included"),
      hint: review ? review.title : t("export.scope.noReview"),
      disabled: !review,
    },
    {
      kind: "selected",
      label: t("export.scope.selected", { count: chosen.length }),
      hint: chosen.length === 0 ? t("export.scope.noneSelected") : undefined,
      disabled: chosen.length === 0,
    },
    {
      kind: "collection",
      label: t("export.scope.collection"),
      hint: userCollections.length === 0 ? t("export.scope.noCollections") : undefined,
      disabled: userCollections.length === 0,
    },
    { kind: "library", label: t("export.scope.library"), disabled: false },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto">
      <header className="border-b border-line px-6 py-4">
        <h1 className="text-h2">{t("export.title")}</h1>
      </header>
      <div className="flex flex-col gap-6 p-6 lg:flex-row lg:items-start">
        <aside className="w-full space-y-6 lg:w-72 lg:shrink-0">
          <fieldset className="space-y-1">
            <legend className="mb-2 text-label uppercase text-fg-muted">
              {t("export.scope.label")}
            </legend>
            {scopeOptions.map((option) => (
              <label
                key={option.kind}
                className="flex cursor-pointer items-start gap-2 rounded-md border border-line bg-raised p-2.5 has-[:checked]:border-primary has-[:checked]:bg-primary-soft has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60"
              >
                <input
                  type="radio"
                  name="export-scope"
                  // The label also wraps the hint; name the choice by its title alone.
                  aria-label={option.label}
                  className="mt-1"
                  value={option.kind}
                  checked={effectiveScope === option.kind}
                  disabled={option.disabled}
                  onChange={() => {
                    setScope(option.kind);
                  }}
                />
                <span className="min-w-0">
                  <span className="block text-ui text-fg">{option.label}</span>
                  {option.hint && (
                    <span className="block truncate text-meta text-fg-muted">{option.hint}</span>
                  )}
                </span>
              </label>
            ))}
            {effectiveScope === "collection" && collection && (
              <select
                aria-label={t("export.scope.chooseCollection")}
                className="mt-2 h-8 w-full rounded-md border border-line bg-raised px-2 text-ui text-fg"
                value={collection.id}
                onChange={(event) => {
                  setCollectionId(event.target.value);
                }}
              >
                {userCollections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {t("export.scope.collectionOption", { name: c.name, count: c.paper_count })}
                  </option>
                ))}
              </select>
            )}
          </fieldset>
          <div className="space-y-2">
            <p className="text-label uppercase text-fg-muted" id="export-format">
              {t("export.format.label")}
            </p>
            <Segmented<ExportFormat>
              aria-label={t("export.format.label")}
              value={choices.format}
              onValueChange={choices.setFormat}
              options={[
                { value: "bibliography", label: t("export.format.bibliography") },
                { value: "bibtex", label: "BibTeX" },
                { value: "ris", label: "RIS" },
              ]}
            />
          </div>
        </aside>

        <main className="min-w-0 flex-1 space-y-6">
          <section className="space-y-3 rounded-md border border-line bg-raised p-4">
            {isBibliography ? (
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex items-center gap-2 text-ui">
                  {t("export.style")}
                  <select
                    className="h-8 rounded-md border border-line bg-surface px-2 text-ui text-fg"
                    value={choices.style}
                    onChange={(event) => {
                      const style = styles.find((s) => s === event.target.value);
                      if (style) choices.setStyle(style);
                    }}
                  >
                    {styles.map((style) => (
                      <option key={style} value={style}>
                        {t(`export.styles.${style}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <Segmented<CslLocale>
                  aria-label={t("export.language")}
                  value={locale}
                  onValueChange={choices.setLocale}
                  options={[
                    { value: "tr-TR", label: "Türkçe" },
                    { value: "en-US", label: "English" },
                  ]}
                />
              </div>
            ) : (
              <CitekeyPreview keys={references.data?.citekeys ?? []} />
            )}

            <div className="flex items-center justify-between gap-2 text-meta text-fg-muted">
              <span>
                {count === undefined ? t("export.loading") : t("export.count", { count })}
              </span>
              {count !== undefined && count > 0 && isBibliography && count > PREVIEW_ENTRIES && (
                <span>{t("export.previewFirst", { count: PREVIEW_ENTRIES })}</span>
              )}
            </div>

            {result.isError ? (
              <p role="alert" className="text-ui text-danger">
                {errorText(t, result.error)}
              </p>
            ) : count === 0 ? (
              <p className="text-ui text-fg-muted">{t("export.empty")}</p>
            ) : isBibliography ? (
              <ol
                aria-label={t("export.preview")}
                className="space-y-2 rounded-md border border-line bg-surface p-4 font-serif text-body"
              >
                {(bibliography.data?.entries ?? []).slice(0, PREVIEW_ENTRIES).map((entry) => (
                  <li key={entry.citekey} className="pl-6 -indent-6">
                    <InlineHtml html={entry.html} />
                  </li>
                ))}
              </ol>
            ) : (
              <pre
                aria-label={t("export.preview")}
                className="max-h-96 overflow-auto rounded-md border border-line bg-surface p-4 font-mono text-meta"
              >
                {(references.data?.content ?? "").split("\n").slice(0, PREVIEW_LINES).join("\n")}
              </pre>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="primary" disabled={!count} onClick={copy}>
                <Clipboard aria-hidden />
                {t("export.copy")}
              </Button>
              <Button disabled={!count} onClick={save}>
                <Download aria-hidden />
                {t("export.save", { fileName })}
              </Button>
              <span role="status" className="text-meta text-fg-muted">
                {notice}
              </span>
            </div>

            <div className="flex items-center gap-2 rounded-md border border-line bg-surface p-2">
              <Terminal className="size-4 shrink-0 text-fg-muted" aria-hidden />
              <code className="min-w-0 flex-1 truncate font-mono text-meta" title={command ?? ""}>
                {command ??
                  t(isBibliography ? "export.command.noBibliography" : "export.command.noSelected")}
              </code>
              <Button
                size="sm"
                variant="ghost"
                disabled={command === null}
                onClick={() => {
                  if (command) run(platform.copyText(command), t("export.copied"));
                }}
              >
                {t("export.command.copy")}
              </Button>
            </div>
          </section>

          {review && (
            <StrategySection
              key={review.id}
              reviewId={review.id}
              onDone={setNotice}
              copy={(text) => platform.copyText(text)}
              save={(name, content, mime) => platform.saveFile(name, content, mime)}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function CitekeyPreview({ keys }: { keys: string[] }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-1">
      <p className="text-ui">
        <span className="text-fg-muted">{t("export.citekey.label")} </span>
        <code className="font-mono text-meta">{t("export.citekey.pattern")}</code>
      </p>
      {keys.length > 0 && (
        <p className="text-meta text-fg-muted">
          {t("export.citekey.examples")}{" "}
          <code className="font-mono">{keys.slice(0, 3).join(", ")}</code>
        </p>
      )}
    </div>
  );
}

function useStrategyLabels(): StrategyLabels {
  const { t } = useTranslation();
  return useMemo(
    () => ({
      headers: [
        t("export.strategy.columns.number"),
        t("export.strategy.columns.source"),
        t("export.strategy.columns.method"),
        t("export.strategy.columns.date"),
        t("export.strategy.columns.query"),
        t("export.strategy.columns.reported"),
        t("export.strategy.columns.retrieved"),
      ],
      source: (row) => {
        const name = t(`search.sources.${row.source}`, row.source);
        return row.file_name ? `${name} (${row.file_name})` : name;
      },
      method: (row) =>
        t(`export.strategy.methods.${row.method}`, { round: row.snowball_round ?? 1 }),
      status: (row) => (row.status === "ok" ? "" : t(`export.strategy.status.${row.status}`)),
      none: "—",
    }),
    [t],
  );
}

function StrategySection({
  reviewId,
  onDone,
  copy,
  save,
}: {
  reviewId: string;
  onDone: (text: string) => void;
  copy: (text: string) => Promise<void>;
  save: (fileName: string, content: string, mime: string) => Promise<void>;
}) {
  const { t } = useTranslation();
  const strategy = useSearchStrategy(reviewId);
  const labels = useStrategyLabels();
  const rows: StrategyRow[] = strategy.data ?? [];
  const markdown = () => strategyMarkdown(rows, labels);
  const after = (work: Promise<void>, done: string) => {
    work.then(
      () => {
        onDone(done);
      },
      () => {
        onDone(t("export.failed"));
      },
    );
  };

  return (
    <section aria-labelledby="strategy-title" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="strategy-title" className="min-w-0 flex-1 text-h3">
          {t("export.strategy.title")}
        </h2>
        <Button
          size="sm"
          disabled={rows.length === 0}
          onClick={() => {
            after(copy(markdown()), t("export.copied"));
          }}
        >
          {t("export.strategy.copyMarkdown")}
        </Button>
        <Button
          size="sm"
          disabled={rows.length === 0}
          onClick={() => {
            after(
              save("search-strategy.md", `${markdown()}\n`, "text/markdown"),
              t("export.saved", { fileName: "search-strategy.md" }),
            );
          }}
        >
          {t("export.strategy.saveMarkdown")}
        </Button>
        <Button
          size="sm"
          disabled={rows.length === 0}
          onClick={() => {
            // A byte-order mark, so spreadsheet programs read the Turkish letters as UTF-8.
            after(
              save(
                "search-strategy.csv",
                `${BYTE_ORDER_MARK}${strategyCsv(rows, labels)}\r\n`,
                "text/csv",
              ),
              t("export.saved", { fileName: "search-strategy.csv" }),
            );
          }}
        >
          {t("export.strategy.saveCsv")}
        </Button>
      </div>
      <p className="text-meta text-fg-muted">{t("export.strategy.hint")}</p>
      {strategy.isError ? (
        <p role="alert" className="text-ui text-danger">
          {errorText(t, strategy.error)}
        </p>
      ) : strategy.isSuccess && rows.length === 0 ? (
        <p className="text-ui text-fg-muted">{t("export.strategy.empty")}</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-line">
          <table className="w-full text-left text-ui">
            <thead className="bg-surface text-meta text-fg-muted">
              <tr>
                {labels.headers.map((header) => (
                  <th key={header} scope="col" className="px-3 py-2 font-medium">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={row.run_id} className="border-t border-line align-top">
                  <td className="px-3 py-2 tabular-nums">{index + 1}</td>
                  <td className="px-3 py-2">{labels.source(row)}</td>
                  <td className="px-3 py-2">{labels.method(row)}</td>
                  <td className="whitespace-nowrap px-3 py-2 tabular-nums">
                    {localDate(row.executed_at)}
                  </td>
                  <td className="px-3 py-2 font-mono text-meta break-all">
                    {row.query ?? labels.none}
                  </td>
                  <td className="px-3 py-2 tabular-nums">{row.total_reported ?? labels.none}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.retrieved}
                    {labels.status(row) && (
                      <span className="text-fg-muted"> ({labels.status(row)})</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
