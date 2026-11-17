// The export screen's server state (Task 40): BibTeX/RIS, formatted bibliographies (Task 39)
// and the search strategy table, each for the scope the user chose.
import { keepPreviousData, useQuery } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type CslStyle = components["schemas"]["CslStyle"];
export type CslLocale = components["schemas"]["CslLocale"];
export type ExportResult = components["schemas"]["ExportResult"];
export type BibliographyResult = components["schemas"]["BibliographyResult"];
export type StrategyRow = components["schemas"]["StrategyRow"];
export type ReferenceFormat = ExportResult["format"];

/** The papers an export is about, as the backend takes them. */
export interface ScopeRequest {
  review_id?: string;
  included?: boolean;
  collection_id?: string;
  paper_ids?: string[];
}

export const exportKeys = {
  references: (format: ReferenceFormat, scope: ScopeRequest) =>
    ["export", "references", format, scope] as const,
  bibliography: (style: CslStyle, locale: CslLocale, scope: ScopeRequest) =>
    ["export", "bibliography", style, locale, scope] as const,
  strategy: (reviewId: string) => ["reviews", reviewId, "search-strategy"] as const,
};

export function useReferences(format: ReferenceFormat, scope: ScopeRequest, enabled: boolean) {
  const api = useApi();
  return useQuery({
    queryKey: exportKeys.references(format, scope),
    enabled,
    staleTime: 0,
    placeholderData: keepPreviousData,
    queryFn: async () =>
      unwrap(
        await api.POST("/export/references", {
          body: { format, ...scope, included: scope.included ?? false },
        }),
      ),
  });
}

export function useBibliography(
  style: CslStyle,
  locale: CslLocale,
  scope: ScopeRequest,
  enabled: boolean,
) {
  const api = useApi();
  // The review scope of a bibliography is always its included studies.
  const body = { ...scope };
  delete body.included;
  return useQuery({
    queryKey: exportKeys.bibliography(style, locale, scope),
    enabled,
    staleTime: 0,
    placeholderData: keepPreviousData,
    queryFn: async () =>
      unwrap(await api.POST("/export/bibliography", { body: { style, locale, ...body } })),
  });
}

export function useSearchStrategy(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: exportKeys.strategy(reviewId),
    staleTime: 0,
    queryFn: async () =>
      unwrap(
        await api.GET("/export/search-strategy", { params: { query: { review_id: reviewId } } }),
      ).rows,
  });
}
