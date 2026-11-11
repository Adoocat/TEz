import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { searchKeys } from "@/features/search/api";
import { unwrap } from "@/lib/api/query";

export type ImportFile = components["schemas"]["ImportFile"];
export type ImportRequest = components["schemas"]["ImportRequest"];
export type ImportPreview = components["schemas"]["ImportPreview"];
export type ImportOutcome = components["schemas"]["ImportOutcome"];
export type ImportIssueView = components["schemas"]["ImportIssueView"];
export type PreviewRecord = components["schemas"]["PreviewRecord"];

// Databases whose exports people import most; anything else is typed in.
export const knownDatabases = ["IEEE Xplore", "ACM DL", "Scopus", "Web of Science"] as const;

export function usePreviewImport() {
  const api = useApi();
  return useMutation({
    mutationFn: async (body: ImportFile) => unwrap(await api.POST("/imports/preview", { body })),
  });
}

export function useRunImport(reviewId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ImportRequest) => unwrap(await api.POST("/imports", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: searchKeys.history(reviewId) }),
  });
}
