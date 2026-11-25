import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

export type FindResults = components["schemas"]["FindResults"];
export type AnchorView = components["schemas"]["AnchorView"];
export type AnchorCreate = components["schemas"]["AnchorCreate"];
export type AnnotationView = components["schemas"]["AnnotationView"];
export type AnnotationCreate = components["schemas"]["AnnotationCreate"];
export type HighlightColor = AnnotationView["color"];

// Design-token names (--color-highlight-<name>). Purple means AI and is not offered.
export const highlightColors = ["yellow", "green", "blue", "pink"] as const;
export const highlightVar = (color: HighlightColor) => `var(--color-highlight-${color})`;

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

export function useAnchor(anchorId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: ["reader", "anchor", anchorId ?? ""] as const,
    enabled: anchorId !== null,
    // A replaced file's anchors are looked up again in the background.
    refetchInterval: (state) => (state.state.data?.status === "checking" ? 1500 : false),
    queryFn: async () =>
      unwrap(
        await api.GET("/anchors/{anchor_id}", {
          params: { path: { anchor_id: anchorId ?? "" } },
        }),
      ),
  });
}

const annotationsKey = (attachmentId: string) => ["reader", "annotations", attachmentId] as const;

export function useAnnotations(attachmentId: string) {
  const api = useApi();
  return useQuery({
    queryKey: annotationsKey(attachmentId),
    // A replaced file's places are looked up again in the background.
    refetchInterval: (state) =>
      state.state.data?.some((a) => a.anchor.status === "checking") ? 1500 : false,
    queryFn: async () =>
      unwrap(
        await api.GET("/attachments/{attachment_id}/annotations", {
          params: { path: { attachment_id: attachmentId } },
        }),
      ),
  });
}

function useInvalidateAnnotations(attachmentId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: annotationsKey(attachmentId) });
}

export function useCreateAnnotation(attachmentId: string) {
  const api = useApi();
  const invalidate = useInvalidateAnnotations(attachmentId);
  return useMutation({
    mutationFn: async (body: AnnotationCreate) =>
      unwrap(
        await api.POST("/attachments/{attachment_id}/annotations", {
          params: { path: { attachment_id: attachmentId } },
          body,
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useUpdateAnnotation(attachmentId: string) {
  const api = useApi();
  const invalidate = useInvalidateAnnotations(attachmentId);
  return useMutation({
    mutationFn: async ({
      id,
      ...changes
    }: {
      id: string;
      color?: HighlightColor;
      comment?: string;
    }) =>
      unwrap(
        await api.PATCH("/annotations/{annotation_id}", {
          params: { path: { annotation_id: id } },
          body: changes,
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useDeleteAnnotation(attachmentId: string) {
  const api = useApi();
  const invalidate = useInvalidateAnnotations(attachmentId);
  return useMutation({
    mutationFn: async (id: string) => {
      unwrapEmpty(
        await api.DELETE("/annotations/{annotation_id}", {
          params: { path: { annotation_id: id } },
        }),
      );
    },
    onSuccess: invalidate,
  });
}
