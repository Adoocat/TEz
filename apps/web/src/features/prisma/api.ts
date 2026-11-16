import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

import type { BoxKey } from "./diagram";

export const prismaKeys = {
  counts: (reviewId: string) => ["reviews", reviewId, "prisma"] as const,
  labels: (reviewId: string) => ["reviews", reviewId, "prisma-labels"] as const,
};

/** Every PRISMA count, derived by the backend on each read. */
export function usePrismaCounts(reviewId: string | undefined) {
  const api = useApi();
  return useQuery({
    queryKey: prismaKeys.counts(reviewId ?? ""),
    enabled: reviewId !== undefined,
    staleTime: 0,
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/prisma", {
          params: { path: { review_id: reviewId ?? "" } },
        }),
      ),
  });
}

export function usePrismaLabels(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: prismaKeys.labels(reviewId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/prisma/labels", {
          params: { path: { review_id: reviewId } },
        }),
      ).labels as Partial<Record<BoxKey, string>>,
  });
}

export function useSaveLabels(reviewId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (labels: Partial<Record<BoxKey, string>>) =>
      unwrap(
        await api.PUT("/reviews/{review_id}/prisma/labels", {
          params: { path: { review_id: reviewId } },
          body: { labels },
        }),
      ),
    onSuccess: (saved) => {
      queryClient.setQueryData(prismaKeys.labels(reviewId), saved.labels);
    },
  });
}
