// The active review's home (design 5.1): research questions, where each stage stands with
// a way to carry on, the latest searches and room for the PRISMA summary (Task 35).
// Every number comes from GET /reviews/{id}/overview, which derives it on each read.
import { ArrowRight, GitBranch } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { useSearchHistory, type SearchOverview } from "@/features/search/api";
import { useSearchView } from "@/features/search/store";

import { useReviewOverview, useReviews, type ReviewView, type StageProgress } from "./api";
import { SnowballPanel } from "@/features/snowballing/SnowballPanel";

import { CriteriaPanel } from "./CriteriaPanel";
import { ReviewWizard } from "./ReviewWizard";
import { useActiveReview } from "./store";

const recentSearchCount = 5;

export function ReviewPanel() {
  const { t } = useTranslation();
  const reviews = useReviews();
  const review = useActiveReview();

  if (reviews.isSuccess && !review) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-6">
        <h1 className="text-h1">{t("reviews.panel.title")}</h1>
        <p className="text-ui text-fg-muted">{t("reviews.panel.none")}</p>
        <ReviewWizard />
      </div>
    );
  }
  if (!review) return null;
  return <Panel review={review} />;
}

function Panel({ review }: { review: ReviewView }) {
  const { t } = useTranslation();
  const overview = useReviewOverview(review.id);

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-h1">{review.title}</h1>
          <span className="rounded-xs border border-line px-1.5 text-meta text-fg-muted">
            {t(`reviews.methods.${review.method}`)}
          </span>
        </div>
        {review.protocol && (
          <p className="max-w-prose text-ui whitespace-pre-line text-fg-muted">{review.protocol}</p>
        )}
      </header>

      <section aria-labelledby="review-questions" className="space-y-2">
        <h2 id="review-questions" className="text-h3">
          {t("reviews.panel.questions")}
        </h2>
        {review.research_questions.length === 0 ? (
          <p className="text-ui text-fg-muted">{t("reviews.panel.noQuestions")}</p>
        ) : (
          <ol className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {review.research_questions.map((question, index) => (
              <li key={question} className="rounded-md border border-line bg-raised p-3">
                <span className="rounded-xs bg-primary px-1.5 font-mono text-meta text-fg-on-accent">
                  {t("reviews.questionCode", { n: index + 1 })}
                </span>
                <p className="mt-2 text-ui">{question}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <CriteriaPanel reviewId={review.id} />
      <SnowballPanel reviewId={review.id} />

      <section aria-labelledby="review-stages" className="space-y-2">
        <h2 id="review-stages" className="text-h3">
          {t("reviews.panel.stages")}
        </h2>
        <ol className="grid gap-2 md:grid-cols-3">
          <SearchStage records={overview.data?.records} />
          {overview.data?.stages.map((stage) => (
            <ScreeningStageCard key={stage.stage} progress={stage} />
          ))}
        </ol>
        {overview.isError && (
          <p role="alert" className="text-meta text-danger">
            {t("reviews.panel.overviewFailed")}
          </p>
        )}
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <RecentSearches reviewId={review.id} />
        <section aria-labelledby="review-prisma" className="space-y-2">
          <h2 id="review-prisma" className="text-h3">
            {t("reviews.panel.prisma")}
          </h2>
          <div className="flex items-start gap-3 rounded-md border border-dashed border-line-strong p-4 text-ui text-fg-muted">
            <GitBranch className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p>{t("reviews.panel.prismaSoon")}</p>
          </div>
        </section>
      </div>
    </div>
  );
}

function useNumber() {
  const { i18n } = useTranslation();
  return (value: number) => value.toLocaleString(i18n.language);
}

function SearchStage({ records }: { records: number | undefined }) {
  const { t } = useTranslation();
  const number = useNumber();
  return (
    <li className="space-y-2 rounded-md border border-line bg-raised p-3">
      <h3 className="text-ui font-medium">{t("reviews.panel.stage.search")}</h3>
      <p className="text-meta text-fg-muted">
        {records === undefined
          ? "…"
          : t("reviews.panel.records", { count: records, n: number(records) })}
      </p>
      <Button asChild size="sm">
        <Link to="/search">
          {t("reviews.panel.toSearch")}
          <ArrowRight />
        </Link>
      </Button>
    </li>
  );
}

function ScreeningStageCard({ progress }: { progress: StageProgress }) {
  const { t } = useTranslation();
  const number = useNumber();
  const name = t(`reviews.panel.stage.${progress.stage}`);
  const share = progress.eligible === 0 ? 0 : progress.decided / progress.eligible;

  return (
    <li className="space-y-2 rounded-md border border-line bg-raised p-3">
      <h3 className="text-ui font-medium">{name}</h3>
      <p className="text-meta">
        <span className={progress.pending > 0 ? "text-fg" : "text-fg-muted"}>
          {t("reviews.panel.pending", { count: progress.pending, n: number(progress.pending) })}
        </span>
        <span className="text-fg-muted">
          {" · "}
          {t("reviews.panel.decided", {
            decided: number(progress.decided),
            eligible: number(progress.eligible),
          })}
        </span>
      </p>
      <div
        role="progressbar"
        aria-label={name}
        aria-valuemin={0}
        aria-valuemax={progress.eligible}
        aria-valuenow={progress.decided}
        className="h-1 overflow-hidden rounded-full bg-line"
      >
        <div className="h-full bg-primary" style={{ width: `${String(share * 100)}%` }} />
      </div>
      <p className="text-meta text-fg-muted">
        <span className="text-success">
          {t("reviews.panel.included", { n: number(progress.included) })}
        </span>
        {" · "}
        <span className="text-danger">
          {t("reviews.panel.excluded", { n: number(progress.excluded) })}
        </span>
        {" · "}
        <span className="text-warning">
          {t("reviews.panel.maybe", { n: number(progress.maybe) })}
        </span>
      </p>
      <Button
        asChild
        size="sm"
        variant={progress.pending > 0 ? "primary" : "secondary"}
        aria-label={t("reviews.panel.continueStage", { stage: name })}
      >
        <Link to={`/screening?stage=${progress.stage}`}>
          {t("reviews.panel.continue")}
          <ArrowRight />
        </Link>
      </Button>
    </li>
  );
}

function RecentSearches({ reviewId }: { reviewId: string }) {
  const { t, i18n } = useTranslation();
  const number = useNumber();
  const history = useSearchHistory(reviewId);
  const openSearch = useSearchView((state) => state.openSearch);
  const navigate = useNavigate();
  const recent = history.data?.slice(0, recentSearchCount) ?? [];
  const label = (search: SearchOverview) => search.file_name ?? search.query;

  return (
    <section aria-labelledby="review-searches" className="space-y-2">
      <h2 id="review-searches" className="text-h3">
        {t("reviews.panel.searches")}
      </h2>
      {history.isSuccess && recent.length === 0 ? (
        <p className="text-ui text-fg-muted">{t("search.historyEmpty")}</p>
      ) : (
        <ul className="divide-y divide-line rounded-md border border-line bg-raised">
          {recent.map((search) => (
            <li key={search.search_id}>
              <button
                type="button"
                className="flex w-full items-baseline gap-3 px-3 py-2 text-left hover:bg-hovered"
                onClick={() => {
                  openSearch(search.search_id);
                  void navigate("/search");
                }}
              >
                <span className="min-w-0 flex-1 truncate font-mono text-meta">{label(search)}</span>
                <span className="shrink-0 text-meta text-fg-muted">
                  {new Date(search.started_at).toLocaleDateString(i18n.language, {
                    dateStyle: "medium",
                  })}
                </span>
                <span className="shrink-0 text-meta text-fg-muted">
                  {t("reviews.panel.unique", { n: number(search.unique) })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
