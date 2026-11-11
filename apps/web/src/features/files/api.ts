import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type PdfAdded = components["schemas"]["PdfAdded"];
export type AttachmentView = components["schemas"]["AttachmentView"];

export const fileKeys = {
  attachments: (paperId: string) => ["papers", paperId, "attachments"] as const,
};

export function isPdf(file: File): boolean {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

/** Sends the PDF as the raw body: no base64, so a 100 MB scan stays 100 MB. */
export function useUploadPdf() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ file, paperId }: { file: File; paperId?: string }) =>
      unwrap(
        await api.POST("/pdfs", {
          params: { query: { file_name: file.name, ...(paperId ? { paper_id: paperId } : {}) } },
          // The generated type says string; the body is the file itself, sent as is.
          body: file as unknown as string,
          bodySerializer: (body: unknown) => body as BodyInit,
          headers: { "Content-Type": "application/pdf" },
        }),
      ),
    onSuccess: (added) =>
      queryClient.invalidateQueries({ queryKey: fileKeys.attachments(added.paper_id) }),
  });
}

export function useAttachments(paperId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: fileKeys.attachments(paperId ?? ""),
    enabled: paperId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/papers/{paper_id}/attachments", {
          params: { path: { paper_id: paperId ?? "" } },
        }),
      ),
  });
}

/** Queue a background download of a free PDF for each paper (arXiv, Unpaywall, OA link). */
export function useFindOpenAccess() {
  const api = useApi();
  return useMutation({
    mutationFn: async (paperIds: string[]) =>
      unwrap(await api.POST("/pdfs/open-access", { body: { paper_ids: paperIds } })),
  });
}
