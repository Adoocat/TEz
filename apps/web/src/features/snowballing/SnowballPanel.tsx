// Snowballing on the review panel (Task 36, Wohlin): pick included papers as seeds, follow
// their references (backward) and the papers citing them (forward) through OpenAlex and
// Semantic Scholar. The worker runs the round; new papers go to title-abstract screening.
import type { TFunction } from "i18next";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { useJobsStore } from "@/features/jobs/store";
import { ApiError } from "@/lib/api/query";

import {
  citationSources,
  directions,
  useRounds,
  useSeeds,
  useStartRound,
  type Direction,
  type SnowballRound,
} from "./api";

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  const params = error instanceof ApiError ? error.params : {};
  return t(`errors.${code}`, { ...params, defaultValue: t("errors.unknown") });
}

export function SnowballPanel({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const seeds = useSeeds(reviewId);
  const rounds = useRounds(reviewId);
  const start = useStartRound(reviewId);
  const [unchecked, setUnchecked] = useState<ReadonlySet<string>>(new Set());
  const [ways, setWays] = useState<ReadonlySet<Direction>>(new Set(directions));
  const [sources, setSources] = useState<ReadonlySet<string>>(new Set(citationSources));
  const all = seeds.data ?? [];
  const chosen = all.filter((seed) => seed.traceable && !unchecked.has(seed.paper_id));

  // When the round's job ends, its finds are in the review: read everything again.
  const jobId = start.data?.job_id;
  const job = useJobsStore((state) => (jobId ? state.jobs[jobId] : undefined));
  const ended = job && ["done", "failed", "cancelled"].includes(job.status);
  useEffect(() => {
    if (ended) void queryClient.invalidateQueries({ queryKey: ["reviews", reviewId] });
  }, [ended, queryClient, reviewId]);

  function toggle<T>(set: ReadonlySet<T>, value: T): Set<T> {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  }

  return (
    <section aria-labelledby="review-snowball" className="space-y-2">
      <h2 id="review-snowball" className="text-h3">
        {t("snowball.title")}
      </h2>
      <p className="text-meta text-fg-muted">{t("snowball.hint")}</p>
      {seeds.isSuccess && all.length === 0 ? (
        <p className="text-ui text-fg-muted">{t("snowball.noSeeds")}</p>
      ) : (
        <form
          aria-label={t("snowball.start")}
          className="space-y-2 rounded-md border border-line bg-raised p-3"
          onSubmit={(event) => {
            event.preventDefault();
            start.mutate({
              paper_ids: chosen.map((seed) => seed.paper_id),
              directions: directions.filter((d) => ways.has(d)),
              sources: citationSources.filter((s) => sources.has(s)),
            });
          }}
        >
          <fieldset className="max-h-48 space-y-1 overflow-y-auto">
            <legend className="text-meta font-semibold text-fg-muted">
              {t("snowball.seeds", { n: chosen.length })}
            </legend>
            {all.map((seed) => (
              <label key={seed.paper_id} className="flex items-start gap-2 text-ui">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4"
                  disabled={!seed.traceable}
                  checked={seed.traceable && !unchecked.has(seed.paper_id)}
                  onChange={() => {
                    setUnchecked(toggle(unchecked, seed.paper_id));
                  }}
                />
                <span className="min-w-0 flex-1">
                  {seed.title}
                  <span className="block text-meta text-fg-muted">
                    {[
                      seed.first_author,
                      seed.year,
                      t(`snowball.includedAt.${seed.included_at}`),
                      seed.round > 0 && t("snowball.foundInRound", { n: seed.round }),
                      seed.followed.length > 0 &&
                        t("snowball.followed", {
                          ways: seed.followed.map((d) => t(`snowball.direction.${d}`)).join(", "),
                        }),
                      !seed.traceable && t("snowball.untraceable"),
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
          <div className="flex flex-wrap gap-4">
            <fieldset className="flex gap-3">
              <legend className="sr-only">{t("snowball.directions")}</legend>
              {directions.map((direction) => (
                <label key={direction} className="flex items-center gap-1 text-ui">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={ways.has(direction)}
                    onChange={() => {
                      setWays(toggle(ways, direction));
                    }}
                  />
                  {t(`snowball.direction.${direction}`)}
                </label>
              ))}
            </fieldset>
            <fieldset className="flex gap-3">
              <legend className="sr-only">{t("snowball.sources")}</legend>
              {citationSources.map((source) => (
                <label key={source} className="flex items-center gap-1 text-ui">
                  <input
                    type="checkbox"
                    className="size-4"
                    checked={sources.has(source)}
                    onChange={() => {
                      setSources(toggle(sources, source));
                    }}
                  />
                  {t(`search.sources.${source}`)}
                </label>
              ))}
            </fieldset>
          </div>
          <Button
            type="submit"
            variant="primary"
            disabled={
              chosen.length === 0 || ways.size === 0 || sources.size === 0 || start.isPending
            }
          >
            {t("snowball.start")}
          </Button>
          {start.data && (
            <p role="status" className="text-meta text-fg-muted">
              {ended
                ? t("snowball.done", { n: start.data.round })
                : t("snowball.running", { n: start.data.round })}
            </p>
          )}
          {start.isError && (
            <p role="alert" className="text-meta text-danger">
              {errorText(t, start.error)}
            </p>
          )}
        </form>
      )}
      {(rounds.data ?? []).length > 0 && (
        <ol aria-label={t("snowball.history")} className="space-y-1">
          {(rounds.data ?? []).map((round) => (
            <RoundRow key={round.search_id} round={round} />
          ))}
        </ol>
      )}
    </section>
  );
}

function RoundRow({ round }: { round: SnowballRound }) {
  const { t, i18n } = useTranslation();
  const date = new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" });
  const failed = round.runs.filter((run) => run.error);
  return (
    <li className="rounded-md border border-line p-2 text-ui">
      <p>
        <span className="font-semibold">{t("snowball.round", { n: round.round })}</span>
        {" · "}
        {date.format(new Date(round.started_at))}
        {" · "}
        {round.directions.map((d) => t(`snowball.direction.${d}`)).join(", ")}
      </p>
      <p className="text-meta text-fg-muted">
        {t("snowball.counts", {
          seeds: round.seeds,
          identified: round.identified,
          added: round.added,
          already: round.already_in_review,
        })}
      </p>
      {failed.length > 0 && (
        <p className="text-meta text-danger">{t("snowball.failedRuns", { n: failed.length })}</p>
      )}
    </li>
  );
}
