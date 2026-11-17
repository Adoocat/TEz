// The "Conflicts" tab of screening (Task 42): agreement and Cohen's kappa per stage, and the
// records two reviewers decided differently, side by side. Reconciling writes the agreed
// decision as a new `consensus` row; neither reviewer's own decision changes.
import type { TFunction } from "i18next";
import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { useActiveReview } from "@/features/reviews/store";
import { useStageCriteria, type ScreeningStage } from "@/features/screening/api";
import { StateBadge } from "@/features/screening/StateBadge";
import { ApiError } from "@/lib/api/query";

import {
  useAgreement,
  useConflicts,
  useReconcile,
  type AgreementView,
  type ConflictView,
  type SideDecision,
} from "./api";

function errorText(t: TFunction, error: unknown): string {
  const code = error instanceof ApiError ? error.code : "unknown";
  return t(`errors.${code}`, { defaultValue: t("errors.unknown") });
}

export function ConflictsPage() {
  const { t } = useTranslation();
  const review = useActiveReview();
  if (!review) {
    return (
      <div className="space-y-2 p-6">
        <h1 className="text-h2">{t("conflicts.title")}</h1>
        <p className="text-ui text-fg-muted">{t("conflicts.noReview")}</p>
      </div>
    );
  }
  return <Conflicts key={review.id} reviewId={review.id} />;
}

function Conflicts({ reviewId }: { reviewId: string }) {
  const { t } = useTranslation();
  const [stage, setStage] = useState<ScreeningStage>("title_abstract");
  const [chosen, setChosen] = useState<string | null>(null);
  const agreement = useAgreement(reviewId, chosen);
  const reviewer = agreement.data?.reviewer ?? null;
  const conflicts = useConflicts(reviewId, stage, reviewer);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-auto">
      <header className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-2">
        <Link
          to="/screening"
          className="inline-flex items-center gap-1 text-ui text-fg-muted hover:text-fg"
        >
          <ArrowLeft className="size-4" aria-hidden />
          {t("conflicts.back")}
        </Link>
        <h1 className="text-h3">{t("conflicts.title")}</h1>
        <div className="flex-1" />
        {(agreement.data?.reviewers.length ?? 0) > 1 && (
          <label className="flex items-center gap-1 text-meta text-fg-muted">
            {t("conflicts.reviewer")}
            <select
              className="h-8 rounded-md border border-line-strong bg-raised px-2 text-ui text-fg"
              value={reviewer ?? ""}
              onChange={(event) => {
                setChosen(event.target.value);
              }}
            >
              {agreement.data?.reviewers.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        )}
        <Segmented<ScreeningStage>
          aria-label={t("screening.stages")}
          value={stage}
          onValueChange={setStage}
          options={[
            { value: "title_abstract", label: t("reviews.panel.stage.title_abstract") },
            { value: "full_text", label: t("reviews.panel.stage.full_text") },
          ]}
        />
      </header>

      <div className="space-y-4 p-4">
        {agreement.isError && (
          <p role="alert" className="text-ui text-danger">
            {errorText(t, agreement.error)}
          </p>
        )}
        {agreement.data && reviewer === null ? (
          <div className="mx-auto max-w-lg space-y-2 p-6 text-center">
            <p className="text-ui">{t("conflicts.noColleague")}</p>
            <Link to="/review" className="text-ui text-primary underline">
              {t("conflicts.toReview")}
            </Link>
          </div>
        ) : (
          agreement.data && (
            <>
              <Agreement agreement={agreement.data} />
              {conflicts.isError ? (
                <p role="alert" className="text-ui text-danger">
                  {errorText(t, conflicts.error)}
                </p>
              ) : conflicts.data?.items.length === 0 ? (
                <p className="rounded-md border border-line bg-raised p-6 text-center text-ui text-fg-muted">
                  {t("conflicts.none")}
                </p>
              ) : (
                <ol aria-label={t("conflicts.list")} className="space-y-3">
                  {conflicts.data?.items.map((item) => (
                    <ConflictItem
                      key={item.paper_id}
                      reviewId={reviewId}
                      stage={stage}
                      reviewer={reviewer ?? ""}
                      item={item}
                    />
                  ))}
                </ol>
              )}
            </>
          )
        )}
      </div>
    </div>
  );
}

function Agreement({ agreement }: { agreement: AgreementView }) {
  const { t, i18n } = useTranslation();
  const percent = new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 1 });
  const kappa = new Intl.NumberFormat(i18n.language, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return (
    <section aria-label={t("conflicts.agreement")} className="grid gap-3 md:grid-cols-2">
      {agreement.stages.map((row) => (
        <div key={row.stage} className="space-y-1 rounded-md border border-line bg-raised p-3">
          <h2 className="text-label uppercase text-fg-muted">
            {t(`reviews.panel.stage.${row.stage}`)}
          </h2>
          {row.compared === 0 ? (
            <p className="text-ui text-fg-muted">{t("conflicts.nothingCompared")}</p>
          ) : (
            <>
              <p className="text-ui tabular-nums">
                {t("conflicts.summary", {
                  percent: percent.format(row.percent ?? 0),
                  kappa: row.kappa === null ? "—" : kappa.format(row.kappa),
                })}
              </p>
              <p className="text-meta text-fg-muted tabular-nums">
                {t("conflicts.counts", {
                  agreed: row.agreed,
                  compared: row.compared,
                  open: row.conflicts,
                })}
              </p>
            </>
          )}
        </div>
      ))}
    </section>
  );
}

function Side({ label, side }: { label: string; side: SideDecision }) {
  return (
    <div className="min-w-0 space-y-1 rounded-md border border-line bg-surface p-2">
      <p className="text-meta text-fg-muted">{label}</p>
      <StateBadge state={side.decision} code={side.criterion_code ?? undefined} />
      {side.criterion_text && <p className="text-meta">{side.criterion_text}</p>}
      {side.note && <p className="text-meta text-fg-muted italic">{side.note}</p>}
    </div>
  );
}

function ConflictItem({
  reviewId,
  stage,
  reviewer,
  item,
}: {
  reviewId: string;
  stage: ScreeningStage;
  reviewer: string;
  item: ConflictView;
}) {
  const { t } = useTranslation();
  const criteria = useStageCriteria(reviewId, stage);
  const reconcile = useReconcile(reviewId, stage);
  const exclusions = (criteria.data ?? []).filter((c) => c.kind === "exclusion");
  const suggested =
    exclusions.find((c) => c.code === item.owner.criterion_code) ??
    exclusions.find((c) => c.code === item.other.criterion_code) ??
    exclusions[0];
  const [reason, setReason] = useState<string>("");
  const reasonId = reason === "" ? (suggested?.id ?? "") : reason;
  const authors =
    item.first_author === null
      ? null
      : item.author_count > 1
        ? t("conflicts.etAl", { name: item.first_author })
        : item.first_author;

  return (
    <li className="space-y-2 rounded-md border border-line bg-raised p-3">
      <div>
        <p className="font-serif text-body">{item.title}</p>
        <p className="text-meta text-fg-muted">
          {[authors, item.year, item.venue].filter((part) => part !== null).join(" · ")}
        </p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <Side label={t("conflicts.you")} side={item.owner} />
        <Side label={reviewer} side={item.other} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-meta text-fg-muted">{t("conflicts.reconcile")}</span>
        <Button
          size="sm"
          disabled={reconcile.isPending}
          onClick={() => {
            reconcile.mutate({ paper_id: item.paper_id, decision: "include" });
          }}
        >
          {t("screening.state.include")}
        </Button>
        <Button
          size="sm"
          disabled={reconcile.isPending}
          onClick={() => {
            reconcile.mutate({ paper_id: item.paper_id, decision: "maybe" });
          }}
        >
          {t("screening.state.maybe")}
        </Button>
        <select
          aria-label={t("conflicts.reason")}
          className="h-7 rounded-md border border-line bg-surface px-1 text-meta text-fg"
          value={reasonId}
          disabled={exclusions.length === 0}
          onChange={(event) => {
            setReason(event.target.value);
          }}
        >
          {exclusions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} · {c.text}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          variant="danger"
          disabled={reconcile.isPending || !reasonId}
          onClick={() => {
            reconcile.mutate({
              paper_id: item.paper_id,
              decision: "exclude",
              criterion_id: reasonId,
            });
          }}
        >
          {t("screening.state.exclude")}
        </Button>
        {reconcile.isError && (
          <span role="alert" className="text-meta text-danger">
            {errorText(t, reconcile.error)}
          </span>
        )}
      </div>
    </li>
  );
}
