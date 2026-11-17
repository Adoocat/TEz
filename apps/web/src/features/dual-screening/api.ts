// Two-reviewer screening (Tasks 41-42): decision files between libraries.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type ImportReport = components["schemas"]["ImportReport"];
export type AgreementView = components["schemas"]["AgreementView"];
export type ConflictView = components["schemas"]["ConflictView"];
export type SideDecision = components["schemas"]["SideDecision"];
export type Reconciliation = components["schemas"]["Reconciliation"];
type Stage = components["schemas"]["ScreeningStage"];

export const dualKeys = {
  reviewers: (reviewId: string) => ["reviews", reviewId, "reviewers"] as const,
  agreement: (reviewId: string, reviewer: string | null) =>
    ["reviews", reviewId, "agreement", reviewer] as const,
  conflicts: (reviewId: string, stage: Stage, reviewer: string | null) =>
    ["reviews", reviewId, "conflicts", stage, reviewer] as const,
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

/** Agreement per stage between the owner and a colleague (the first by name when null). */
export function useAgreement(reviewId: string, reviewer: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: dualKeys.agreement(reviewId, reviewer),
    staleTime: 0,
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/decisions/agreement", {
          params: { path: { review_id: reviewId }, query: reviewer ? { reviewer } : {} },
        }),
      ),
  });
}

export function useConflicts(reviewId: string, stage: Stage, reviewer: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: dualKeys.conflicts(reviewId, stage, reviewer),
    staleTime: 0,
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/decisions/conflicts/{stage}", {
          params: {
            path: { review_id: reviewId, stage },
            query: reviewer ? { reviewer } : {},
          },
        }),
      ),
  });
}

/** The agreed decision for a conflict, written as a `consensus` row. */
export function useReconcile(reviewId: string, stage: Stage) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Reconciliation) =>
      unwrap(
        await api.POST("/reviews/{review_id}/decisions/conflicts/{stage}/reconcile", {
          params: { path: { review_id: reviewId, stage } },
          body,
        }),
      ),
    // Conflicts, agreement, PRISMA and the included studies all follow.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reviews", reviewId] }),
  });
}
