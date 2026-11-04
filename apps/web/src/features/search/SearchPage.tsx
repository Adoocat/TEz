// The systematic search screen (design 4.2): query, sources and their state, summary, the
// deduplicated results, and the history of searches in this review.
import { Play } from "lucide-react";
import { useCallback, useMemo, useState, type KeyboardEvent, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";
import { ReviewForm } from "@/features/reviews/ReviewForm";
import { useActiveReview } from "@/features/reviews/store";
import { useReviews } from "@/features/reviews/api";
import { ApiError } from "@/lib/api/query";

import {
  sourceNames,
  useAddToLibrary,
  useAddToReview,
  useSearchOverview,
  useSearchResults,
  useStartSearch,
  type SearchResultRow,
  type SourceName,
} from "./api";
import {
  availableOptions,
  filterRows,
  noFilters,
  type ResultFilters,
  type VenueType,
} from "./filters";
import { ResultList } from "./ResultList";
import { SearchHistory } from "./SearchHistory";
import { SourceChips, SourceProblems } from "./SourceChips";
import { useSearchView } from "./store";
import { useSearchProgress } from "./useSearchProgress";

type Tab = "results" | "history";

// Per source. Systematic searches want breadth; the backend allows up to 5000.
const RESULT_LIMIT = 1000;

function parseYear(text: string): number | null {
  const value = Number.parseInt(text, 10);
  return Number.isNaN(value) ? null : value;
}

export function SearchPage() {
  const { t } = useTranslation();
  const reviews = useReviews();
  const review = useActiveReview();
  const { activeSearchId, openSearch } = useSearchView();
  const [tab, setTab] = useState<Tab>("results");

  if (reviews.isSuccess && !review) {
    return (
      <div className="mx-auto max-w-md space-y-4 p-6">
        <h1 className="text-h1">{t("search.title")}</h1>
        <p className="text-ui text-fg-muted">{t("search.needReview")}</p>
        <ReviewForm />
      </div>
    );
  }
  if (!review) return null;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex items-center justify-between gap-3 px-4 pt-3 pb-2">
        <h1 className="text-h2">{t("search.title")}</h1>
        <Segmented
          aria-label={t("search.view")}
          value={tab}
          onValueChange={setTab}
          options={[
            { value: "results", label: t("search.results") },
            { value: "history", label: t("search.historyTab") },
          ]}
        />
      </header>
      {tab === "results" ? (
        <Results reviewId={review.id} searchId={activeSearchId} onStarted={openSearch} />
      ) : (
        <SearchHistory
          reviewId={review.id}
          onOpen={(searchId) => {
            openSearch(searchId);
            setTab("results");
          }}
        />
      )}
    </div>
  );
}

function Results({
  reviewId,
  searchId,
  onStarted,
}: {
  reviewId: string;
  searchId: string | null;
  onStarted: (searchId: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const { selectedPaperId, selectPaper } = useSearchView();
  const start = useStartSearch();
  const progress = useSearchProgress(searchId);
  const overview = useSearchOverview(searchId);
  const results = useSearchResults(searchId);
  const [query, setQuery] = useState("");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [enabled, setEnabled] = useState<ReadonlySet<SourceName>>(new Set(sourceNames));
  const [filters, setFilters] = useState<ResultFilters>(noFilters);
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set());

  const running = progress.running || start.isPending;
  const rows: SearchResultRow[] = useMemo(() => results.data ?? [], [results.data]);
  const visible = useMemo(() => filterRows(rows, filters), [rows, filters]);
  const options = useMemo(() => availableOptions(rows), [rows]);
  const runs = overview.data?.search_id === searchId ? overview.data.runs : [];
  const number = (value: number) => value.toLocaleString(i18n.language);
  const yearsInvalid = (() => {
    const from = parseYear(yearFrom);
    const to = parseYear(yearTo);
    return from !== null && to !== null && from > to;
  })();
  const canStart = query.trim() !== "" && enabled.size > 0 && !running && !yearsInvalid;

  function submit(event?: SyntheticEvent) {
    event?.preventDefault();
    if (!canStart) return;
    start.mutate(
      {
        review_id: reviewId,
        query: query.trim(),
        sources: sourceNames.filter((source) => enabled.has(source)),
        year_from: parseYear(yearFrom),
        year_to: parseYear(yearTo),
        limit: RESULT_LIMIT,
      },
      {
        onSuccess: ({ search_id }) => {
          setChecked(new Set());
          setFilters(noFilters);
          onStarted(search_id);
        },
      },
    );
  }

  function submitWithKeyboard(event: KeyboardEvent) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) submit();
  }

  function toggleSource(source: SourceName) {
    setEnabled((current) => {
      const next = new Set(current);
      if (!next.delete(source)) next.add(source);
      return next;
    });
  }

  // Stable, so checking one row does not redraw the others.
  const togglePaper = useCallback((paperId: string) => {
    setChecked((current) => {
      const next = new Set(current);
      if (!next.delete(paperId)) next.add(paperId);
      return next;
    });
  }, []);

  const allVisibleChecked = visible.length > 0 && visible.every((row) => checked.has(row.paper_id));

  return (
    <>
      <form onSubmit={submit} className="space-y-2 border-b border-line px-4 pb-3">
        <textarea
          aria-label={t("search.queryLabel")}
          className="block h-20 w-full resize-y rounded-md border border-line-strong bg-raised p-2 font-mono text-meta text-fg placeholder:text-fg-muted"
          placeholder={t("search.queryPlaceholder")}
          value={query}
          maxLength={4000}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          onKeyDown={submitWithKeyboard}
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1 text-meta text-fg-muted">
            {t("search.yearFrom")}
            <Input
              className="h-7 w-20"
              inputMode="numeric"
              value={yearFrom}
              aria-invalid={yearsInvalid}
              onChange={(event) => {
                setYearFrom(event.target.value);
              }}
            />
          </label>
          <label className="flex items-center gap-1 text-meta text-fg-muted">
            {t("search.yearTo")}
            <Input
              className="h-7 w-20"
              inputMode="numeric"
              value={yearTo}
              aria-invalid={yearsInvalid}
              onChange={(event) => {
                setYearTo(event.target.value);
              }}
            />
          </label>
          <div className="flex-1" />
          <Button type="submit" variant="primary" disabled={!canStart}>
            <Play aria-hidden />
            {running ? t("search.running") : t("search.start")}
          </Button>
        </div>
        <SourceChips
          enabled={enabled}
          onToggle={toggleSource}
          live={progress.sources}
          runs={runs}
          disabled={running}
        />
        {start.error && (
          <p role="alert" className="text-meta text-danger">
            {t(`errors.${start.error instanceof ApiError ? start.error.code : "unknown"}`, {
              defaultValue: t("errors.unknown"),
            })}
          </p>
        )}
        <SourceProblems runs={runs} />
        {runs.length > 0 && (
          <details className="text-meta">
            <summary className="cursor-pointer text-primary">{t("search.translated")}</summary>
            <dl className="mt-1 space-y-1">
              {runs.map((run) => (
                <div key={run.source} className="flex gap-2">
                  <dt className="w-32 shrink-0 text-fg-muted">
                    {t(`search.sources.${run.source}`, run.source)}
                  </dt>
                  <dd className="font-mono break-all">{run.translated_query}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
      </form>

      {searchId === null ? (
        <p className="p-6 text-center text-ui text-fg-muted">{t("search.firstSearch")}</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line bg-surface px-4 py-1.5">
            <label className="flex items-center gap-2 text-meta">
              <input
                type="checkbox"
                className="size-4"
                aria-label={t("search.selectAll")}
                checked={allVisibleChecked}
                disabled={visible.length === 0}
                onChange={() => {
                  setChecked(
                    allVisibleChecked ? new Set() : new Set(visible.map((row) => row.paper_id)),
                  );
                }}
              />
            </label>
            {overview.data?.search_id === searchId && (
              <span aria-live="polite" className="text-meta text-fg-muted">
                {t("search.summary", {
                  sources: overview.data.runs.length,
                  retrieved: number(overview.data.retrieved),
                  duplicates: number(overview.data.duplicates),
                  unique: number(overview.data.unique),
                  inLibrary: number(overview.data.in_library),
                })}
              </span>
            )}
            <div className="flex-1" />
            <ResultFilterBar
              filters={filters}
              onChange={setFilters}
              venueTypes={options.venueTypes}
              languages={options.languages}
            />
            <BulkActions reviewId={reviewId} searchId={searchId} paperIds={[...checked]} />
          </div>
          {visible.length > 0 ? (
            <ResultList
              rows={visible}
              checked={checked}
              selectedId={selectedPaperId}
              onToggle={togglePaper}
              onSelect={selectPaper}
            />
          ) : (
            <p className="p-6 text-center text-ui text-fg-muted">
              {running ? t("search.waitingForSources") : t("search.noResults")}
            </p>
          )}
        </>
      )}
    </>
  );
}

function ResultFilterBar({
  filters,
  onChange,
  venueTypes,
  languages,
}: {
  filters: ResultFilters;
  onChange: (filters: ResultFilters) => void;
  venueTypes: VenueType[];
  languages: string[];
}) {
  const { t } = useTranslation();
  const selectClass = "h-7 rounded-md border border-line bg-raised px-1 text-meta text-fg";
  return (
    <div className="flex items-center gap-2">
      <select
        aria-label={t("search.filterType")}
        className={selectClass}
        value={filters.venueType ?? ""}
        onChange={(event) => {
          onChange({ ...filters, venueType: (event.target.value || null) as VenueType | null });
        }}
      >
        <option value="">{t("search.allTypes")}</option>
        {venueTypes.map((type) => (
          <option key={type} value={type}>
            {t(`search.venueTypes.${type}`)}
          </option>
        ))}
      </select>
      <select
        aria-label={t("search.filterLanguage")}
        className={selectClass}
        value={filters.language ?? ""}
        onChange={(event) => {
          onChange({ ...filters, language: event.target.value || null });
        }}
      >
        <option value="">{t("search.allLanguages")}</option>
        {languages.map((language) => (
          <option key={language} value={language}>
            {language}
          </option>
        ))}
      </select>
      <label className="flex items-center gap-1 text-meta text-fg-muted">
        <input
          type="checkbox"
          className="size-3.5"
          checked={filters.openAccessOnly}
          onChange={(event) => {
            onChange({ ...filters, openAccessOnly: event.target.checked });
          }}
        />
        {t("search.onlyOpenAccess")}
      </label>
    </div>
  );
}

function BulkActions({
  reviewId,
  searchId,
  paperIds,
}: {
  reviewId: string;
  searchId: string;
  paperIds: string[];
}) {
  const { t } = useTranslation();
  const toReview = useAddToReview(reviewId, searchId);
  const toLibrary = useAddToLibrary(searchId);
  const none = paperIds.length === 0;
  const outcome = toReview.data ?? toLibrary.data;
  const failed = toReview.isError || toLibrary.isError;

  return (
    <div className="flex items-center gap-2">
      <span aria-live="polite" className="text-meta text-fg-muted">
        {failed
          ? t("search.addFailed")
          : outcome &&
            t("search.added", { added: outcome.added, present: outcome.already_present })}
      </span>
      <Button
        size="sm"
        variant="primary"
        disabled={none || toReview.isPending}
        onClick={() => {
          toLibrary.reset();
          toReview.mutate(paperIds);
        }}
      >
        {t("search.addToReview", { count: paperIds.length })}
      </Button>
      <Button
        size="sm"
        disabled={none || toLibrary.isPending}
        onClick={() => {
          toReview.reset();
          toLibrary.mutate(paperIds);
        }}
      >
        {t("search.addToLibrary", { count: paperIds.length })}
      </Button>
    </div>
  );
}
