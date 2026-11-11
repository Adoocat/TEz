// Every search in the review: the raw material of the method section (design 4.2).
import { useTranslation } from "react-i18next";

import { useSearchHistory, type SearchOverview } from "./api";

export function SearchHistory({
  reviewId,
  onOpen,
}: {
  reviewId: string;
  onOpen: (searchId: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const history = useSearchHistory(reviewId);
  const number = (value: number) => value.toLocaleString(i18n.language);
  // An import carries only the day the user searched the database: no time to show.
  const when = (search: SearchOverview) =>
    search.file_name
      ? new Date(search.started_at).toLocaleDateString(i18n.language, {
          dateStyle: "medium",
          timeZone: "UTC",
        })
      : new Date(search.started_at).toLocaleString(i18n.language, {
          dateStyle: "medium",
          timeStyle: "short",
        });

  if (history.data?.length === 0) {
    return <p className="p-6 text-ui text-fg-muted">{t("search.historyEmpty")}</p>;
  }

  return (
    <div className="min-h-0 flex-1 overflow-auto px-4 pb-4">
      <table className="w-full text-left text-ui">
        <thead className="sticky top-0 bg-canvas text-meta text-fg-muted">
          <tr className="border-b border-line">
            <th className="h-row pr-3 font-normal">{t("search.history.date")}</th>
            <th className="pr-3 font-normal">{t("search.history.query")}</th>
            <th className="pr-3 font-normal">{t("search.history.sources")}</th>
            <th className="pr-3 font-normal">{t("search.history.filters")}</th>
            <th className="pr-3 text-right font-normal">{t("search.history.reported")}</th>
            <th className="pr-3 text-right font-normal">{t("search.history.retrieved")}</th>
            <th className="text-right font-normal">{t("search.history.unique")}</th>
          </tr>
        </thead>
        <tbody>
          {history.data?.map((search) => (
            <tr key={search.search_id} className="border-b border-line align-top hover:bg-hovered">
              <td className="py-2 pr-3 whitespace-nowrap text-fg-muted">
                {when(search)}
                <div className="text-meta">{t(`search.history.via.${search.initiated_via}`)}</div>
              </td>
              <td className="py-2 pr-3">
                <button
                  type="button"
                  className="text-left font-mono text-meta text-fg underline-offset-2 hover:underline"
                  onClick={() => {
                    onOpen(search.search_id);
                  }}
                >
                  {search.file_name ? (
                    <span className="font-sans">
                      {t("search.history.imported", { file: search.file_name })}
                    </span>
                  ) : (
                    search.query
                  )}
                </button>
                {search.file_name && search.query && (
                  <div className="font-mono text-meta text-fg-muted">{search.query}</div>
                )}
              </td>
              <td className="py-2 pr-3 text-meta">
                {search.runs.map((run) => (
                  <div key={run.source}>
                    {t(`search.sources.${run.source}`, run.source)}
                    <span className={run.status === "ok" ? "text-fg-muted" : "text-danger"}>
                      {" "}
                      · {t(`search.history.status.${run.status}`)}
                    </span>
                  </div>
                ))}
              </td>
              <td className="py-2 pr-3 text-meta text-fg-muted">{yearRange(search, t)}</td>
              <td className="py-2 pr-3 text-right">{number(totalReported(search))}</td>
              <td className="py-2 pr-3 text-right">{number(search.retrieved)}</td>
              <td className="py-2 text-right">{number(search.unique)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function totalReported(search: SearchOverview): number {
  return search.runs.reduce((sum, run) => sum + (run.total_reported ?? 0), 0);
}

function yearRange(search: SearchOverview, t: (key: string) => string): string {
  const from = search.filters?.year_from as number | null | undefined;
  const to = search.filters?.year_to as number | null | undefined;
  if (from == null && to == null) return t("search.history.allYears");
  return `${String(from ?? "…")} – ${String(to ?? "…")}`;
}
