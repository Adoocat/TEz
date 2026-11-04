import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type ReviewView = components["schemas"]["ReviewView"];
export type ReviewMethod = components["schemas"]["ReviewMethod"];

export const reviewMethods: ReviewMethod[] = ["prisma2020", "kitchenham_slr"];

const reviewsKey = ["reviews"] as const;

export function useReviews() {
  const api = useApi();
  return useQuery({
    queryKey: reviewsKey,
    queryFn: async () => unwrap(await api.GET("/reviews")),
  });
}

export function useCreateReview() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: { title: string; method: ReviewMethod }) =>
      unwrap(await api.POST("/reviews", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: reviewsKey }),
  });
}
