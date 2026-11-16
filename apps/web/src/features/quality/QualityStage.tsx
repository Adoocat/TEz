// The quality stage on the review panel (design 5.1): a card in the stage list while the
// stage is on, and the switch that turns the optional stage on or off.
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";

import { useQualitySummary, useSetQualityEnabled } from "./api";

function useNumber() {
  const { i18n } = useTranslation();
  return (value: number) => value.toLocaleString(i18n.language);
}

/** The stage card; nothing at all while the stage is off. */
export function QualityStageCard({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const number = useNumber();
  const summary = useQualitySummary(reviewId);
  const data = summary.data;
  if (!data?.enabled) return null;

  const name = t("quality.stage");
  const pending = data.papers - data.assessed;
  return (
    <li className="space-y-2 rounded-md border border-line bg-raised p-3">
      <h3 className="text-ui font-medium">{name}</h3>
      <p className="text-meta">
        <span className={pending > 0 ? "text-fg" : "text-fg-muted"}>
          {t("reviews.panel.pending", { count: pending, n: number(pending) })}
        </span>
        <span className="text-fg-muted">
          {" · "}
          {t("quality.assessedOf", {
            assessed: number(data.assessed),
            papers: number(data.papers),
          })}
        </span>
      </p>
      <div
        role="progressbar"
        aria-label={name}
        aria-valuemin={0}
        aria-valuemax={data.papers}
        aria-valuenow={data.assessed}
        className="h-1 overflow-hidden rounded-full bg-line"
      >
        <div
          className="h-full bg-primary"
          style={{
            width: `${String(data.papers === 0 ? 0 : (data.assessed / data.papers) * 100)}%`,
          }}
        />
      </div>
      <p className="text-meta text-fg-muted">
        {data.questions === 0
          ? t("quality.noQuestionsYet")
          : t("quality.questionCount", { count: data.questions, n: number(data.questions) })}
      </p>
      <Button
        asChild
        size="sm"
        variant={pending > 0 ? "primary" : "secondary"}
        aria-label={t("reviews.panel.continueStage", { stage: name })}
      >
        <Link to="/quality">
          {t("reviews.panel.continue")}
          <ArrowRight />
        </Link>
      </Button>
    </li>
  );
}

/** Turns the optional stage on or off; off hides it but keeps every answer. */
export function QualityToggle({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const summary = useQualitySummary(reviewId);
  const setEnabled = useSetQualityEnabled(reviewId);
  const enabled = summary.data?.enabled ?? false;

  return (
    <div className="space-y-1">
      <label className="flex items-center gap-2 text-ui">
        <input
          type="checkbox"
          className="size-4"
          checked={enabled}
          disabled={!summary.isSuccess || setEnabled.isPending}
          onChange={(event) => {
            setEnabled.mutate(event.target.checked);
          }}
        />
        {t("quality.toggle")}
      </label>
      <p className="text-meta text-fg-muted">{t("quality.toggleHint")}</p>
    </div>
  );
}
