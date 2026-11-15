import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

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

// --- screening criteria (Task 25) ---

export type CriterionView = components["schemas"]["CriterionView"];
export type CriterionCreate = components["schemas"]["CriterionCreate"];
export type CriterionUpdate = components["schemas"]["CriterionUpdate"];
export type CriterionKind = components["schemas"]["CriterionKind"];
export type ScreeningStage = components["schemas"]["ScreeningStage"];

export const criteriaKey = (reviewId: string) => ["reviews", reviewId, "criteria"] as const;

export function useCriteria(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: criteriaKey(reviewId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/criteria", {
          params: { path: { review_id: reviewId } },
        }),
      ),
  });
}

function useCriteriaMutation<T>(reviewId: string, mutationFn: (input: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: () => queryClient.invalidateQueries({ queryKey: criteriaKey(reviewId) }),
  });
}

export function useAddCriterion(reviewId: string) {
  const api = useApi();
  return useCriteriaMutation(reviewId, async (body: CriterionCreate) =>
    unwrap(
      await api.POST("/reviews/{review_id}/criteria", {
        params: { path: { review_id: reviewId } },
        body,
      }),
    ),
  );
}

export function useUpdateCriterion(reviewId: string) {
  const api = useApi();
  return useCriteriaMutation(reviewId, async ({ id, ...body }: CriterionUpdate & { id: string }) =>
    unwrap(
      await api.PATCH("/reviews/{review_id}/criteria/{criterion_id}", {
        params: { path: { review_id: reviewId, criterion_id: id } },
        body,
      }),
    ),
  );
}

export function useDeleteCriterion(reviewId: string) {
  const api = useApi();
  return useCriteriaMutation(reviewId, async (criterionId: string) => {
    unwrapEmpty(
      await api.DELETE("/reviews/{review_id}/criteria/{criterion_id}", {
        params: { path: { review_id: reviewId, criterion_id: criterionId } },
      }),
    );
  });
}

export function useReorderCriteria(reviewId: string) {
  const api = useApi();
  return useCriteriaMutation(reviewId, async (criterionIds: string[]) =>
    unwrap(
      await api.PUT("/reviews/{review_id}/criteria/order", {
        params: { path: { review_id: reviewId } },
        body: { criterion_ids: criterionIds },
      }),
    ),
  );
}
