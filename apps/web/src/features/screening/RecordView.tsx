// One record in focus mode (design 5.2): big serif title, authors, year, venue, and the
// abstract with the criteria's terms highlighted.
import { Fragment, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/cn";
import { highlight } from "@/lib/text";

import type { ScreeningRecord, StageCriterion } from "./api";
import { StateBadge } from "./StateBadge";

const MAX_AUTHORS = 6;

export function Highlighted({
  text,
  criteria,
  inHeading = false,
}: {
  text: string;
  criteria: readonly StageCriterion[];
  /** In a heading, matches are plain spans without a tooltip: a `mark` or a `title` there
   * would change the heading's accessible name. */
  inHeading?: boolean;
}) {
  const terms = useMemo(
    () =>
      criteria.flatMap((criterion) =>
        criterion.keywords.map((term) => ({ term, value: criterion })),
      ),
    [criteria],
  );
  const segments = useMemo(() => highlight(text, terms), [text, terms]);
  const Match = inHeading ? "span" : "mark";
  return (
    <>
      {segments.map((segment, index) =>
        segment.match ? (
          <Match
            // Pieces never move within one text, so their place is a stable key.
            key={index}
            title={inHeading ? undefined : segment.match.code}
            data-criterion={segment.match.code}
            className={cn(
              "rounded-xs bg-transparent text-inherit",
              segment.match.kind === "inclusion"
                ? "bg-success/15"
                : "underline decoration-danger decoration-2 underline-offset-2",
            )}
          >
            {segment.text}
          </Match>
        ) : (
          // Plain text stays a text node, so the spaces around a match keep the name whole.
          <Fragment key={index}>{segment.text}</Fragment>
        ),
      )}
    </>
  );
}

export function RecordView({
  record,
  criteria,
  pendingNote,
}: {
  record: ScreeningRecord;
  criteria: readonly StageCriterion[];
  pendingNote: string | undefined;
}) {
  const { t, i18n } = useTranslation();
  const number = new Intl.NumberFormat(i18n.language);
  const authors =
    record.authors.length > MAX_AUTHORS
      ? `${record.authors.slice(0, MAX_AUTHORS).join(", ")} ${t("screening.record.moreAuthors", { n: record.authors.length - MAX_AUTHORS })}`
      : record.authors.join(", ");
  const note = record.decision?.note ?? pendingNote;
  const code = criteria.find((c) => c.id === record.decision?.criterion_id)?.code;

  return (
    <article aria-labelledby="screening-title" className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-meta text-fg-muted">
        <span className="rounded-xs border border-line px-1.5 font-mono">
          {t("screening.record.position", {
            position: number.format(record.position),
            total: number.format(record.total),
          })}
        </span>
        <StateBadge state={record.state} code={code} />
      </div>
      {record.retraction_status !== "none" && (
        <p role="alert" className="rounded-md border border-danger p-2 text-meta text-danger">
          {t(`screening.record.retraction.${record.retraction_status}`)}
        </p>
      )}
      <h1 id="screening-title" className="font-serif text-h1 text-balance">
        <Highlighted text={record.title} criteria={criteria} inHeading />
      </h1>
      <p className="text-ui text-fg-muted">
        {[authors || t("screening.record.noAuthors"), record.year, record.venue]
          .filter(Boolean)
          .join(" · ")}
        {record.doi && (
          <>
            {" · "}
            <span className="font-mono text-meta">DOI {record.doi}</span>
          </>
        )}
      </p>
      <section
        aria-labelledby="screening-abstract"
        className="rounded-lg border border-line bg-raised p-4"
      >
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 id="screening-abstract" className="text-meta font-semibold text-fg-muted uppercase">
            {t("screening.record.abstract")}
          </h2>
          {criteria.some((c) => c.keywords.length > 0) && (
            <p className="flex gap-3 text-meta text-fg-muted">
              <span className="rounded-xs bg-success/15 px-1">
                {t("screening.record.legendInclusion")}
              </span>
              <span className="underline decoration-danger decoration-2 underline-offset-2">
                {t("screening.record.legendExclusion")}
              </span>
            </p>
          )}
        </div>
        {record.abstract ? (
          <p className="font-serif text-reading">
            <Highlighted text={record.abstract} criteria={criteria} />
          </p>
        ) : (
          <p className="text-ui text-fg-muted">{t("screening.record.noAbstract")}</p>
        )}
      </section>
      {note && (
        <section aria-label={t("screening.note.title")} className="text-ui">
          <h2 className="text-meta font-semibold text-fg-muted">{t("screening.note.title")}</h2>
          <p className="whitespace-pre-wrap">{note}</p>
        </section>
      )}
    </article>
  );
}
