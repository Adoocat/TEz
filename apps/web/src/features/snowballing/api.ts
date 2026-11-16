import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type SnowballSeed = components["schemas"]["SnowballSeed"];
export type SnowballRound = components["schemas"]["SnowballRoundView"];
export type SnowballStart = components["schemas"]["SnowballStart"];
export type Direction = SnowballSeed["followed"][number];

export const citationSources = ["openalex", "semantic_scholar"] as const;
export const directions: Direction[] = ["backward", "forward"];

export const snowballKeys = {
  all: (reviewId: string) => ["reviews", reviewId, "snowball"] as const,
  seeds: (reviewId: string) => ["reviews", reviewId, "snowball", "seeds"] as const,
  rounds: (reviewId: string) => ["reviews", reviewId, "snowball", "rounds"] as const,
};

export function useSeeds(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: snowballKeys.seeds(reviewId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/snowball/seeds", {
          params: { path: { review_id: reviewId } },
        }),
      ),
  });
}

export function useRounds(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: snowballKeys.rounds(reviewId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/snowball", {
          params: { path: { review_id: reviewId } },
        }),
      ),
  });
}

export function useStartRound(reviewId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Omit<SnowballStart, "limit" | "initiated_via">) =>
      unwrap(
        await api.POST("/reviews/{review_id}/snowball", {
          params: { path: { review_id: reviewId } },
          body: { ...body, limit: 1000, initiated_via: "gui" },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: snowballKeys.all(reviewId) }),
  });
}
