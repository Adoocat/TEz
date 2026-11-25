// Search inside PDFs (design 4.3 "Tam metin arama sonuçları"): papers by their best page, each
// with the passages that match. A passage opens the reader at its page.
import { FileText } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/query";

import { useFulltextSearch, type FulltextPaper, type SnippetPart } from "./api";

const FIRST = 30;
const ALL = 200;

export function FulltextResults({
  query,
  paperIds,
  onSelect,
}: {
  query: string;
  /** The papers the list shows: its scope and filters. */
  paperIds: string[];
  onSelect: (paperId: string) => void;
}) {
  const { t, i18n } = useTranslation();
  // "Show more" belongs to the query it was pressed for.
  const [moreFor, setMoreFor] = useState<string | null>(null);
  const limit = moreFor === query ? ALL : FIRST;
  const search = useFulltextSearch(query, paperIds, limit);

  if (query.trim() === "") {
    return <p className="p-6 text-center text-ui text-fg-muted">{t("library.fulltext.hint")}</p>;
  }
  if (search.isError) {
    const code = search.error instanceof ApiError ? search.error.code : "unknown";
    return (
      <p role="alert" className="p-6 text-center text-ui text-danger">
        {t(`errors.${code}`, { defaultValue: t("errors.unknown") })}
      </p>
    );
  }
  if (!search.data) {
    return (
      <p role="status" className="p-6 text-center text-ui text-fg-muted">
        {t("library.fulltext.searching")}
      </p>
    );
  }
  const { papers, total_papers: total, total_pages: pages, truncated } = search.data;
  if (papers.length === 0) {
    return <p className="p-6 text-center text-ui text-fg-muted">{t("library.fulltext.none")}</p>;
  }
  const number = (value: number) => value.toLocaleString(i18n.language) + (truncated ? "+" : "");
  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <p role="status" className="px-4 py-2 text-meta text-fg-muted">
        {t("library.fulltext.papers", { count: total, n: number(total) })} ·{" "}
        {t("library.fulltext.pages", { count: pages, n: number(pages) })}
      </p>
      <ul aria-label={t("library.fulltext.results")}>
        {papers.map((paper) => (
          <Result key={paper.paper_id} paper={paper} query={query} onSelect={onSelect} />
        ))}
      </ul>
      {total > papers.length && (
        <div className="p-4 text-center text-meta text-fg-muted">
          {limit === FIRST ? (
            <Button
              size="sm"
              onClick={() => {
                setMoreFor(query);
              }}
            >
              {t("library.fulltext.more")}
            </Button>
          ) : (
            t("library.fulltext.narrow", { shown: papers.length })
          )}
        </div>
      )}
    </div>
  );
}

function Result({
  paper,
  query,
  onSelect,
}: {
  paper: FulltextPaper;
  query: string;
  onSelect: (paperId: string) => void;
}) {
  const { t } = useTranslation();
  const byline = [
    paper.first_author &&
      (paper.author_count > 1
        ? t("library.fulltext.andOthers", { author: paper.first_author })
        : paper.first_author),
    paper.year,
  ]
    .filter(Boolean)
    .join(" · ");
  const rest = paper.page_hits - paper.pages.length;
  return (
    <li className="border-t border-line px-4 py-3">
      <button
        type="button"
        className="block max-w-full truncate text-left text-ui font-medium text-fg hover:underline"
        onClick={() => {
          onSelect(paper.paper_id);
        }}
      >
        {paper.title}
      </button>
      {byline && <p className="text-meta text-fg-muted">{byline}</p>}
      <ul className="mt-1 space-y-1">
        {paper.pages.map((page) => (
          <li key={`${page.attachment_id}-${String(page.page)}`}>
            <Link
              to={`/reader/${page.attachment_id}?${new URLSearchParams({
                page: String(page.page),
                find: query.trim(),
              }).toString()}`}
              className="flex items-start gap-2 rounded-md px-2 py-1 hover:bg-hovered"
            >
              <span className="mt-0.5 inline-flex shrink-0 items-center gap-1 rounded-xs border border-line px-1.5 text-meta text-fg-muted tabular-nums">
                <FileText aria-hidden className="size-3" />
                {t("library.fulltext.page", { page: page.page })}
              </span>
              <span className="min-w-0 text-ui text-fg-muted">
                <Passage parts={page.snippet} />
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {rest > 0 && (
        <p className="mt-1 px-2 text-meta text-fg-muted">
          {t("library.fulltext.morePages", { count: rest })}
        </p>
      )}
    </li>
  );
}

function Passage({ parts }: { parts: SnippetPart[] }) {
  return parts.map((part, index) =>
    part.hit ? (
      <mark
        // The parts of a passage never change order.
        key={index}
        className="rounded-xs bg-[color-mix(in_srgb,var(--color-highlight-yellow)_45%,transparent)] text-fg"
      >
        {part.text}
      </mark>
    ) : (
      <span key={index}>{part.text}</span>
    ),
  );
}
