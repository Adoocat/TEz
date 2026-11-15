// The active review in the title bar, and the way to start a new one.
import { Plus } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

import { useReviews } from "./api";
import { ReviewWizard } from "./ReviewWizard";
import { useActiveReview, useActiveReviewStore } from "./store";

export function ReviewPicker() {
  const { t } = useTranslation();
  const reviews = useReviews();
  const active = useActiveReview();
  const setActiveReview = useActiveReviewStore((state) => state.setActiveReview);
  const [dialogOpen, setDialogOpen] = useState(false);

  return (
    <div className="flex items-center gap-1">
      {active && (
        <select
          aria-label={t("reviews.active")}
          className="h-7 max-w-64 truncate rounded-md border border-line bg-raised px-2 text-ui text-fg"
          value={active.id}
          onChange={(event) => {
            setActiveReview(event.target.value);
          }}
        >
          {reviews.data?.map((review) => (
            <option key={review.id} value={review.id}>
              {review.title}
            </option>
          ))}
        </select>
      )}
      <Dialog.Root open={dialogOpen} onOpenChange={setDialogOpen}>
        <Dialog.Trigger asChild>
          <Button variant="ghost" size="icon" aria-label={t("reviews.new")}>
            <Plus />
          </Button>
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-fg/30" />
          <Dialog.Content
            aria-describedby={undefined}
            className="fixed top-1/4 left-1/2 w-lg max-w-[90vw] -translate-x-1/2 space-y-3 rounded-lg border border-line bg-raised p-4 shadow-popover"
          >
            <Dialog.Title className="text-h3">{t("reviews.new")}</Dialog.Title>
            <ReviewWizard
              onCreated={() => {
                setDialogOpen(false);
              }}
            />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
