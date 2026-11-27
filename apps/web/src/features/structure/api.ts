// A paper's sections and references read by GROBID (Task 56). Optional: everything here is
// hidden while no GROBID address is set.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type StructureView = components["schemas"]["StructureView"];

const key = (attachmentId: string) => ["attachments", attachmentId, "structure"] as const;

/** What a reading changes: when it was read, or why it failed. */
export function stampOf(view: StructureView | undefined): string | null {
  return view ? `${view.read_at ?? ""}|${view.error ?? ""}` : null;
}

/** Asked again every two seconds while it still says what it said when a reading was asked. */
export function useStructure(attachmentId: string, waitingFor: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: key(attachmentId),
    refetchInterval: (query) =>
      waitingFor !== null && stampOf(query.state.data) === waitingFor ? 2000 : false,
    queryFn: async () =>
      unwrap(
        await api.GET("/attachments/{attachment_id}/structure", {
          params: { path: { attachment_id: attachmentId } },
        }),
      ),
  });
}

export function useReadStructure(attachmentId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/attachments/{attachment_id}/structure", {
          params: { path: { attachment_id: attachmentId } },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key(attachmentId) }),
  });
}
