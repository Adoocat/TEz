// Saved searches of databases without an open API (Task 27): the database and the query the
// user runs on its site. "Open site" opens it in the browser and copies the query; each new
// export is imported against the saved search, which says how many records are new.
import { Copy, ExternalLink, FileUp } from "lucide-react";
import { useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { useBackend } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  databaseNamed,
  databaseSite,
  defaultDatabase,
  knownDatabases,
} from "@/features/imports/databases";
import { ImportDialog } from "@/features/imports/ImportDialog";

import { useExternalSearches, useSaveExternalSearch, type ExternalSearchView } from "./api";

const OTHER = "other";

export function ExternalSearches({
  reviewId,
  onShowResults,
}: {
  reviewId: string;
  onShowResults: (searchId: string) => void;
}) {
  const { t } = useTranslation();
  const saved = useExternalSearches(reviewId);
  const [importing, setImporting] = useState<string | null>(null);

  return (
    <div className="min-h-0 flex-1 space-y-4 overflow-auto px-4 pb-4">
      <p className="max-w-prose text-meta text-fg-muted">{t("search.external.intro")}</p>
      <SaveForm reviewId={reviewId} />
      {saved.isSuccess && saved.data.length === 0 && (
        <p className="text-ui text-fg-muted">{t("search.external.empty")}</p>
      )}
      {saved.data && saved.data.length > 0 && (
        <ul
          aria-label={t("search.external.listLabel")}
          className="divide-y divide-line rounded-md border border-line bg-raised"
        >
          {saved.data.map((search) => (
            <SavedSearch
              key={search.id}
              search={search}
              onImport={() => {
                setImporting(search.id);
              }}
            />
          ))}
        </ul>
      )}
      <ImportDialog
        reviewId={reviewId}
        open={importing !== null}
        savedSearchId={importing}
        onOpenChange={(open) => {
          if (!open) setImporting(null);
        }}
        onShowResults={onShowResults}
      />
    </div>
  );
}

function SaveForm({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const save = useSaveExternalSearch(reviewId);
  const [database, setDatabase] = useState<string>(defaultDatabase);
  const [otherDatabase, setOtherDatabase] = useState("");
  const [query, setQuery] = useState("");
  const source = database === OTHER ? otherDatabase.trim() : database;
  const guide = databaseNamed(source);

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    if (!source || !query.trim()) return;
    save.mutate(
      { review_id: reviewId, source, query: query.trim(), name: null },
      {
        onSuccess: () => {
          setQuery("");
        },
      },
    );
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-wrap items-end gap-2 rounded-md border border-line bg-raised p-3"
    >
      <label className="space-y-1">
        <span className="block text-meta text-fg-muted">{t("imports.database")}</span>
        <select
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
      </label>
      {database === OTHER && (
        <label className="space-y-1">
          <span className="block text-meta text-fg-muted">{t("imports.otherDatabaseName")}</span>
          <Input
            maxLength={64}
            value={otherDatabase}
            onChange={(event) => {
              setOtherDatabase(event.target.value);
            }}
          />
        </label>
      )}
      <label className="min-w-64 flex-1 space-y-1">
        <span className="block text-meta text-fg-muted">{t("search.external.query")}</span>
        <Input
          className="font-mono"
          maxLength={4000}
          placeholder={t("imports.queryPlaceholder")}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
          }}
        />
      </label>
      <Button type="submit" disabled={!source || !query.trim() || save.isPending}>
        {t("search.external.save")}
      </Button>
      {guide && (
        <p className="basis-full text-meta text-fg-muted">
          <span className="font-medium text-fg">{t("search.external.howToExport")}</span>{" "}
          {t(`search.external.guides.${guide.key}`)}
        </p>
      )}
      {save.isError && (
        <p role="alert" className="basis-full text-meta text-danger">
          {t("search.external.saveFailed")}
        </p>
      )}
    </form>
  );
}

function SavedSearch({ search, onImport }: { search: ExternalSearchView; onImport: () => void }) {
  const { t, i18n } = useTranslation();
  const { platform } = useBackend();
  const [copied, setCopied] = useState(false);
  const site = databaseSite(search.source);
  const day = (iso: string) =>
    new Date(iso).toLocaleDateString(i18n.language, { dateStyle: "medium", timeZone: "UTC" });

  async function copyQuery() {
    await navigator.clipboard.writeText(search.query);
    setCopied(true);
  }

  return (
    <li className="space-y-1 px-3 py-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-ui font-medium">{search.source}</span>
        {search.name !== search.query && (
          <span className="text-meta text-fg-muted">{search.name}</span>
        )}
      </div>
      <p className="font-mono text-meta break-all">{search.query}</p>
      <p className="text-meta text-fg-muted">
        {search.imports === 0 || search.last_searched_at === null
          ? t("search.external.notImported")
          : t("search.external.imported", {
              count: search.imports,
              date: day(search.last_searched_at),
              records: (search.last_retrieved ?? 0).toLocaleString(i18n.language),
            })}
      </p>
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {site && (
          <Button
            size="sm"
            onClick={() => {
              void copyQuery().then(() => platform.openExternal(site));
            }}
          >
            <ExternalLink />
            {t("search.external.openSite")}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            void copyQuery();
          }}
        >
          <Copy />
          {t("search.external.copyQuery")}
        </Button>
        <Button size="sm" variant="ghost" onClick={onImport}>
          <FileUp />
          {t("search.external.importNew")}
        </Button>
        {copied && (
          <span role="status" className="text-meta text-fg-muted">
            {t("search.external.copied")}
          </span>
        )}
      </div>
    </li>
  );
}
