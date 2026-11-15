import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type ReviewView = components["schemas"]["ReviewView"];
export type ReviewCreate = components["schemas"]["ReviewCreate"];
export type ReviewMethod = components["schemas"]["ReviewMethod"];
export type ReviewOverview = components["schemas"]["ReviewOverview"];
export type StageProgress = components["schemas"]["StageProgress"];

// PRISMA 2020 first: it is the default for a new review (ADR 0019).
export const reviewMethods: ReviewMethod[] = ["prisma2020", "kitchenham_slr"];

export const reviewKeys = {
  all: ["reviews"] as const,
  overview: (reviewId: string) => ["reviews", reviewId, "overview"] as const,
};

export function useReviews() {
  const api = useApi();
  return useQuery({
    queryKey: reviewKeys.all,
    queryFn: async () => unwrap(await api.GET("/reviews")),
  });
}

export function useCreateReview() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ReviewCreate) => unwrap(await api.POST("/reviews", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewKeys.all }),
  });
}

/** The review panel's counts; the backend derives them on every read. */
export function useReviewOverview(reviewId: string | undefined) {
  const api = useApi();
  return useQuery({
    queryKey: reviewKeys.overview(reviewId ?? ""),
    enabled: reviewId !== undefined,
    staleTime: 0,
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/overview", {
          params: { path: { review_id: reviewId ?? "" } },
        }),
      ),
  });
}
