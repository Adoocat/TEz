// Two-reviewer screening (Tasks 41-42): decision files between libraries.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type ImportReport = components["schemas"]["ImportReport"];

export const dualKeys = {
  reviewers: (reviewId: string) => ["reviews", reviewId, "reviewers"] as const,
};

export function useReviewers(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: dualKeys.reviewers(reviewId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/decisions/reviewers", {
          params: { path: { review_id: reviewId } },
        }),
      ),
  });
}

/** The owner's decisions as a decision file, under the name they give. */
export function useExportDecisions(reviewId: string) {
  const api = useApi();
  return useMutation({
    mutationFn: async (reviewer: string) =>
      unwrap(
        await api.GET("/reviews/{review_id}/decisions/export", {
          params: { path: { review_id: reviewId }, query: { reviewer } },
        }),
      ),
  });
}

export function useImportDecisions(reviewId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (content: string) =>
      unwrap(
        await api.POST("/reviews/{review_id}/decisions/import", {
          params: { path: { review_id: reviewId } },
          body: { content },
        }),
      ),
    // New decisions change reviewers, agreement and conflicts.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reviews", reviewId] }),
  });
}
