// Quality assessment (Task 38): an optional stage, reached from the review panel. Two views:
// the question set (own questions, any scale, or a bundled template) and assessing the
// studies included at full text. Tool-neutral (ADR 0019).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { useActiveReview } from "@/features/reviews/store";

import { useQuality, useSetQualityEnabled, type QuestionView } from "./api";
import { AssessView } from "./AssessView";
import { errorText, QuestionSet } from "./QuestionSet";

type View = "assess" | "questions";

export function QualityPage() {
  const { t } = useTranslation();
  const review = useActiveReview();
  if (!review) {
    return (
      <div className="mx-auto max-w-lg space-y-2 p-6">
        <h1 className="text-h1">{t("quality.title")}</h1>
        <p className="text-ui text-fg-muted">{t("quality.noReview")}</p>
        <Link to="/review" className="text-ui text-primary underline">
          {t("quality.toReview")}
        </Link>
      </div>
    );
  }
  return <Quality key={review.id} reviewId={review.id} />;
}

function Quality({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const quality = useQuality(reviewId);
  const setEnabled = useSetQualityEnabled(reviewId);

  if (quality.isError) {
    return (
      <p role="alert" className="p-6 text-ui text-danger">
        {errorText(t, quality.error)}
      </p>
    );
  }
  if (!quality.data) return null;

  if (!quality.data.enabled) {
    return (
      <div className="mx-auto max-w-lg space-y-3 p-6">
        <h1 className="text-h1">{t("quality.title")}</h1>
        <p className="text-ui text-fg-muted">{t("quality.off")}</p>
        <Button
          variant="primary"
          disabled={setEnabled.isPending}
          onClick={() => {
            setEnabled.mutate(true);
          }}
        >
          {t("quality.turnOn")}
        </Button>
      </div>
    );
  }

  // Start where the work is: set up questions first, then assess.
  return (
    <Enabled
      reviewId={reviewId}
      questions={quality.data.questions}
      initialView={quality.data.questions.length === 0 ? "questions" : "assess"}
    />
  );
}

function Enabled({
  reviewId,
  questions,
  initialView,
}: {
  reviewId: string;
  questions: QuestionView[];
  initialView: View;
}) {
  const { t } = useTranslation();
  const [shown, setView] = useState<View>(initialView);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-h1">{t("quality.title")}</h1>
        <Segmented
          aria-label={t("quality.view")}
          value={shown}
          onValueChange={setView}
          options={[
            { value: "assess", label: t("quality.assess") },
            { value: "questions", label: t("quality.questionSet") },
          ]}
        />
        <Link to="/review" className="ml-auto text-ui text-primary underline">
          {t("quality.toReview")}
        </Link>
      </header>
      {shown === "questions" ? (
        <QuestionSet reviewId={reviewId} questions={questions} />
      ) : (
        <AssessView reviewId={reviewId} questions={questions} />
      )}
    </div>
  );
}
