// Deleting a review moves it to the trash (its searches and decisions are append-only, so they
// stay); the trash lists such reviews and brings them back.
import { RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { ApiError } from "@/lib/api/query";

import { useDeletedReviews, useDeleteReview, useRestoreReview, type ReviewView } from "./api";
import { useActiveReviewStore } from "./store";

function errorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : "unknown";
}

/** The panel's "Delete review" button, with a confirmation. */
export function DeleteReviewButton({ review }: { review: ReviewView }) {
  const { t } = useTranslation();
  const remove = useDeleteReview();
  const [asking, setAsking] = useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => {
          setAsking(true);
        }}
      >
        <Trash2 aria-hidden />
        {t("reviews.trash.delete")}
      </Button>
      <ConfirmDialog
        open={asking}
        title={t("reviews.trash.confirmTitle", { title: review.title })}
        description={t("reviews.trash.confirmText")}
        confirmLabel={t("reviews.trash.delete")}
        cancelLabel={t("reviews.trash.cancel")}
        onConfirm={() => {
          setAsking(false);
          remove.mutate(review.id);
        }}
        onCancel={() => {
          setAsking(false);
        }}
      />
      {remove.isError && (
        <p role="alert" className="text-meta text-danger">
          {t(`errors.${errorCode(remove.error)}`, { defaultValue: t("errors.unknown") })}
        </p>
      )}
    </>
  );
}

/** Reviews in the trash, each with a way back. Nothing is shown when the trash is empty. */
export function ReviewTrash() {
  const { t } = useTranslation();
  const deleted = useDeletedReviews();
  const restore = useRestoreReview();
  const setActiveReview = useActiveReviewStore((state) => state.setActiveReview);
  const list = deleted.data ?? [];
  if (list.length === 0) return null;

  return (
    <section aria-labelledby="review-trash" className="space-y-2">
      <h2 id="review-trash" className="text-h3">
        {t("reviews.trash.title", { count: list.length })}
      </h2>
      <p className="text-meta text-fg-muted">{t("reviews.trash.hint")}</p>
      <ul className="divide-y divide-line rounded-md border border-line">
        {list.map((review) => (
          <li key={review.id} className="flex items-center gap-3 p-2.5 text-ui">
            <span className="min-w-0 flex-1 truncate">{review.title}</span>
            <Button
              size="sm"
              disabled={restore.isPending}
              aria-label={t("reviews.trash.restoreNamed", { title: review.title })}
              onClick={() => {
                restore.mutate(review.id, {
                  onSuccess: () => {
                    setActiveReview(review.id);
                  },
                });
              }}
            >
              <RotateCcw aria-hidden />
              {t("reviews.trash.restore")}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}
