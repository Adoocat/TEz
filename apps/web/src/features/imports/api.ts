import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { searchKeys } from "@/features/search/api";
import { unwrap } from "@/lib/api/query";

// The file part of a preview or import request (the backend has no endpoint taking it alone).
export type ImportFile = Pick<ImportPreviewRequest, "file_name" | "content_base64" | "path">;
export type ImportPreviewRequest = components["schemas"]["ImportPreviewRequest"];
export type ImportRequest = components["schemas"]["ImportRequest"];
export type ImportPreview = components["schemas"]["ImportPreview"];
export type ImportOutcome = components["schemas"]["ImportOutcome"];
export type ImportIssueView = components["schemas"]["ImportIssueView"];
export type PreviewRecord = components["schemas"]["PreviewRecord"];

export function usePreviewImport() {
  const api = useApi();
  return useMutation({
    mutationFn: async (body: ImportPreviewRequest) =>
      unwrap(await api.POST("/imports/preview", { body })),
  });
}

export function useRunImport(reviewId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: ImportRequest) => unwrap(await api.POST("/imports", { body })),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: searchKeys.history(reviewId) }),
        queryClient.invalidateQueries({ queryKey: searchKeys.external(reviewId) }),
      ]),
  });
}
