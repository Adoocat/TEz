// The small review form (owner's decision for Task 14): a title and a method. Research
// questions, criteria and the setup wizard (design 4.1) come later.
import { useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Segmented } from "@/components/ui/segmented";

import { reviewMethods, useCreateReview, type ReviewMethod, type ReviewView } from "./api";
import { useActiveReviewStore } from "./store";

export function ReviewForm({ onCreated }: { onCreated?: (review: ReviewView) => void }) {
  const { t } = useTranslation();
  const create = useCreateReview();
  const setActiveReview = useActiveReviewStore((state) => state.setActiveReview);
  const [title, setTitle] = useState("");
  const [method, setMethod] = useState<ReviewMethod>("kitchenham_slr");

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    create.mutate(
      { title: trimmed, method },
      {
        onSuccess: (review) => {
          setActiveReview(review.id);
          setTitle("");
          onCreated?.(review);
        },
      },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <label className="block space-y-1">
        <span className="text-meta text-fg-muted">{t("reviews.titleLabel")}</span>
        <Input
          value={title}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
          placeholder={t("reviews.titlePlaceholder")}
          maxLength={300}
        />
      </label>
      <div className="space-y-1">
        <span className="block text-meta text-fg-muted">{t("reviews.methodLabel")}</span>
        <Segmented
          aria-label={t("reviews.methodLabel")}
          value={method}
          onValueChange={setMethod}
          options={reviewMethods.map((value) => ({
            value,
            label: t(`reviews.methods.${value}`),
          }))}
        />
      </div>
      {create.isError && (
        <p role="alert" className="text-meta text-danger">
          {t("reviews.createFailed")}
        </p>
      )}
      <Button type="submit" variant="primary" disabled={!title.trim() || create.isPending}>
        {t("reviews.create")}
      </Button>
    </form>
  );
}
