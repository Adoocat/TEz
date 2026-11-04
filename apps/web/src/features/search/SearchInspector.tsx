// The selected result: everything known about it, and how its records were merged.
import { useTranslation } from "react-i18next";

import { useSearchResults } from "./api";
import { useSearchView } from "./store";

export function SearchInspector() {
  const { t } = useTranslation();
  const { activeSearchId, selectedPaperId } = useSearchView();
  const results = useSearchResults(activeSearchId);
  const row = results.data?.find((candidate) => candidate.paper_id === selectedPaperId);

  if (!row) {
    return <p className="text-meta text-fg-muted">{t("search.inspectorEmpty")}</p>;
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-h3">{row.title}</h2>
        <p className="text-meta text-fg-muted">
          {[
            row.first_author && row.author_count > 1
              ? t("search.andOthers", { name: row.first_author })
              : row.first_author,
            row.year,
            row.venue,
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {row.is_retracted && <p className="text-meta text-danger">{t("search.retractedNotice")}</p>}
      </div>

      <dl className="space-y-1 text-meta">
        {row.doi && <Identifier label="DOI" value={row.doi} href={`https://doi.org/${row.doi}`} />}
        {row.arxiv_id && (
          <Identifier
            label="arXiv"
            value={row.arxiv_id}
            href={`https://arxiv.org/abs/${row.arxiv_id}`}
          />
        )}
        {row.oa_url && (
          <Identifier
            label={t("search.openAccess")}
            value={t("search.openPdf")}
            href={row.oa_url}
          />
        )}
      </dl>

      <section className="space-y-1">
        <h3 className="text-meta text-fg-muted">{t("search.mergedFrom")}</h3>
        <ul className="space-y-1 text-meta">
          {row.sources.map((source) => (
            <li
              key={`${source.source}-${String(source.rank)}`}
              className="rounded-md border border-line bg-canvas px-2 py-1"
            >
              <span className="font-medium">
                {t(`search.sources.${source.source}`, source.source)}
              </span>
              {" · "}
              {t("search.rank", { rank: source.rank })}
              {" · "}
              {t(`search.matchMethods.${source.match_method}`)}
              {source.match_method === "title_fuzzy" &&
                source.match_score !== null &&
                ` (%${String(Math.round(source.match_score * 100))})`}
            </li>
          ))}
        </ul>
      </section>

      {row.abstract && (
        <section className="space-y-1">
          <h3 className="text-meta text-fg-muted">{t("search.abstract")}</h3>
          <p className="font-serif text-ui">{row.abstract}</p>
        </section>
      )}
    </div>
  );
}

function Identifier({ label, value, href }: { label: string; value: string; href: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-fg-muted">{label}</dt>
      <dd className="min-w-0 truncate">
        <a href={href} target="_blank" rel="noreferrer" className="text-primary hover:underline">
          {value}
        </a>
      </dd>
    </div>
  );
}
