// Which review is active, remembered on this device (design-prompt §3, title bar).
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { useReviews, type ReviewView } from "./api";

interface ActiveReviewState {
  activeReviewId: string | null;
  setActiveReview: (id: string) => void;
}

export const useActiveReviewStore = create<ActiveReviewState>()(
  persist(
    (set) => ({
      activeReviewId: null,
      setActiveReview: (id) => {
        set({ activeReviewId: id });
      },
    }),
    { name: "tez.review", storage: createJSONStorage(() => localStorage) },
  ),
);

/** The review searches belong to: the remembered one, or else the newest there is. */
export function useActiveReview(): ReviewView | undefined {
  const reviews = useReviews();
  const activeId = useActiveReviewStore((state) => state.activeReviewId);
  const all = reviews.data ?? [];
  return all.find((review) => review.id === activeId) ?? all.at(-1);
}
