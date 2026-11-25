import { useQuery } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export type FindResults = components["schemas"]["FindResults"];

/** Where a text is in one document. Off for an empty query. */
export function useFind(attachmentId: string, query: string) {
  const api = useApi();
  const q = query.trim();
  return useQuery({
    queryKey: ["reader", "find", attachmentId, q] as const,
    enabled: q !== "",
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === attachmentId ? previous : undefined,
    // The text may still be on its way from the worker.
    refetchInterval: (state) => (state.state.data?.text === "pending" ? 1500 : false),
    queryFn: async () =>
      unwrap(
        await api.GET("/attachments/{attachment_id}/find", {
          params: { path: { attachment_id: attachmentId }, query: { q } },
        }),
      ),
  });
}
