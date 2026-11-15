import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type SearchStart = components["schemas"]["SearchStart"];
export type SearchOverview = components["schemas"]["SearchOverview"];
export type SearchResultRow = components["schemas"]["SearchResultRow"];
export type SourceProgress = components["schemas"]["SourceProgress"];
export type RunView = components["schemas"]["RunView"];
export type ExternalSearchView = components["schemas"]["ExternalSearchView"];
export type ExternalSearchCreate = components["schemas"]["ExternalSearchCreate"];

// DBLP is postponed: dblp.org answers API clients with a bot check (ADR 0008).
export const sourceNames = [
  "openalex",
  "semantic_scholar",
  "arxiv",
  "crossref",
  "pubmed",
  "europepmc",
] as const;
// The sources a theses-only search can ask (Task 28); the backend refuses the others.
export const thesisFilterSources: readonly string[] = ["openalex", "crossref"];
export type SourceName = (typeof sourceNames)[number];

export const searchKeys = {
  history: (reviewId: string) => ["searches", "history", reviewId] as const,
  external: (reviewId: string) => ["searches", "external", reviewId] as const,
  overview: (searchId: string) => ["searches", searchId, "overview"] as const,
  results: (searchId: string) => ["searches", searchId, "results"] as const,
};

export function useStartSearch() {
  const api = useApi();
  return useMutation({
    mutationFn: async (body: SearchStart) => unwrap(await api.POST("/searches", { body })),
  });
}

export function useSearchOverview(searchId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: searchKeys.overview(searchId ?? ""),
    enabled: searchId !== null,
    // A search that has not recorded any source yet has nothing to show: not an error.
    retry: false,
    queryFn: async () =>
      unwrap(
        await api.GET("/searches/{search_id}", { params: { path: { search_id: searchId ?? "" } } }),
      ),
  });
}

export function useSearchResults(searchId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: searchKeys.results(searchId ?? ""),
    enabled: searchId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/searches/{search_id}/results", {
          params: { path: { search_id: searchId ?? "" } },
        }),
      ),
  });
}

export function useSearchHistory(reviewId: string | undefined) {
  const api = useApi();
  return useQuery({
    queryKey: searchKeys.history(reviewId ?? ""),
    enabled: reviewId !== undefined,
    queryFn: async () =>
      unwrap(await api.GET("/searches", { params: { query: { review_id: reviewId ?? "" } } })),
  });
}

function useInvalidateSearch() {
  const queryClient = useQueryClient();
  return (searchId: string) =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: searchKeys.results(searchId) }),
      queryClient.invalidateQueries({ queryKey: searchKeys.overview(searchId) }),
    ]);
}

export function useAddToReview(reviewId: string | undefined, searchId: string | null) {
  const api = useApi();
  const invalidate = useInvalidateSearch();
  return useMutation({
    mutationFn: async (paperIds: string[]) =>
      unwrap(
        await api.POST("/reviews/{review_id}/records", {
          params: { path: { review_id: reviewId ?? "" } },
          body: { paper_ids: paperIds, search_id: searchId },
        }),
      ),
    onSuccess: () => invalidate(searchId ?? ""),
  });
}

export function useAddToLibrary(searchId: string | null) {
  const api = useApi();
  const invalidate = useInvalidateSearch();
  return useMutation({
    mutationFn: async (paperIds: string[]) =>
      unwrap(await api.POST("/library/papers", { body: { paper_ids: paperIds } })),
    onSuccess: () => invalidate(searchId ?? ""),
  });
}

/** Saved searches of databases without an open API (Task 27). */
export function useExternalSearches(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: searchKeys.external(reviewId),
    queryFn: async () =>
      unwrap(await api.GET("/searches/external", { params: { query: { review_id: reviewId } } })),
  });
}

export function useSaveExternalSearch(reviewId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ExternalSearchCreate) =>
      unwrap(await api.POST("/searches/external", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: searchKeys.external(reviewId) }),
  });
}
