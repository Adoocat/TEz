import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

export type CollectionView = components["schemas"]["CollectionView"];
export type TagView = components["schemas"]["TagView"];
export type LibraryPaperRow = components["schemas"]["LibraryPaperRow"];
export type ReadingStatus = components["schemas"]["ReadingStatus"];
export type ChangeCount = components["schemas"]["ChangeCount"];
export type PaperDetail = components["schemas"]["PaperDetail"];

export const readingStatuses: ReadingStatus[] = ["unread", "reading", "read"];
// Tag colours are design-token names (--color-highlight-<name>), never raw values.
export const tagColors = ["yellow", "green", "blue", "pink", "purple"] as const;

export interface PaperScope {
  kind: "all" | "collection" | "tag";
  id?: string;
}

export const libraryKeys = {
  all: ["library"] as const,
  collections: ["library", "collections"] as const,
  tags: ["library", "tags"] as const,
  papers: (scope: PaperScope) => ["library", "papers", scope.kind, scope.id ?? ""] as const,
};

/** Everything under "library" changes together: counts, lists and memberships. */
function useInvalidateLibrary() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: libraryKeys.all });
}

export function useCollections() {
  const api = useApi();
  return useQuery({
    queryKey: libraryKeys.collections,
    queryFn: async () => unwrap(await api.GET("/collections")),
  });
}

export function useTags() {
  const api = useApi();
  return useQuery({
    queryKey: libraryKeys.tags,
    queryFn: async () => unwrap(await api.GET("/tags")),
  });
}

export function useLibraryPapers(scope: PaperScope) {
  const api = useApi();
  return useQuery({
    queryKey: libraryKeys.papers(scope),
    queryFn: async () =>
      unwrap(
        await api.GET("/papers", {
          params: {
            query: {
              ...(scope.kind === "collection" && scope.id ? { collection_id: scope.id } : {}),
              ...(scope.kind === "tag" && scope.id ? { tag_id: scope.id } : {}),
            },
          },
        }),
      ),
  });
}

/** Metadata full-text search; ids best first. Off for an empty query. */
export function useLibrarySearch(query: string) {
  const api = useApi();
  const q = query.trim();
  return useQuery({
    queryKey: ["library", "search", q] as const,
    enabled: q !== "",
    placeholderData: (previous) => previous,
    queryFn: async () => unwrap(await api.GET("/papers/search", { params: { query: { q } } })),
  });
}

function paperDetailQuery(api: ReturnType<typeof useApi>, paperId: string | null) {
  return {
    queryKey: ["library", "paper", paperId ?? ""] as const,
    queryFn: async () =>
      unwrap(
        await api.GET("/papers/{paper_id}", { params: { path: { paper_id: paperId ?? "" } } }),
      ),
  };
}

export function usePaperDetail(paperId: string | null) {
  const api = useApi();
  return useQuery({ ...paperDetailQuery(api, paperId), enabled: paperId !== null });
}

/** The file "Open PDF" opens: a readable PDF first; a broken one can still be tried. */
export function readablePdf(paper: PaperDetail) {
  return (
    paper.attachments.find((a) => a.kind === "pdf" && a.text_status !== "failed") ??
    paper.attachments[0]
  );
}

/** Fetches (or reuses) a paper's detail to find the file to open. */
export function usePdfToOpen() {
  const api = useApi();
  const queryClient = useQueryClient();
  return async (paperId: string) =>
    readablePdf(await queryClient.query(paperDetailQuery(api, paperId)));
}

export function useUpdateCitekey() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async ({ id, citekey }: { id: string; citekey: string }) =>
      unwrap(
        await api.PATCH("/papers/{paper_id}", {
          params: { path: { paper_id: id } },
          body: { citekey },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useCreateCollection() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async (body: { name: string; parent_id: string | null }) =>
      unwrap(await api.POST("/collections", { body })),
    onSuccess: invalidate,
  });
}

export function useUpdateCollection() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; name?: string; parent_id?: string | null }) =>
      unwrap(
        await api.PATCH("/collections/{collection_id}", {
          params: { path: { collection_id: id } },
          body,
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useDeleteCollection() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrapEmpty(
        await api.DELETE("/collections/{collection_id}", {
          params: { path: { collection_id: id } },
        }),
      );
    },
    onSuccess: invalidate,
  });
}

export function useFileInCollection() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async ({ id, paperIds }: { id: string; paperIds: string[] }) =>
      unwrap(
        await api.POST("/collections/{collection_id}/papers", {
          params: { path: { collection_id: id } },
          body: { paper_ids: paperIds },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useRemoveFromCollection() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async ({ id, paperIds }: { id: string; paperIds: string[] }) =>
      unwrap(
        await api.POST("/collections/{collection_id}/papers/remove", {
          params: { path: { collection_id: id } },
          body: { paper_ids: paperIds },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useCreateTag() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async (body: { name: string; color: string | null }) =>
      unwrap(await api.POST("/tags", { body })),
    onSuccess: invalidate,
  });
}

export function useUpdateTag() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; name?: string; color?: string | null }) =>
      unwrap(await api.PATCH("/tags/{tag_id}", { params: { path: { tag_id: id } }, body })),
    onSuccess: invalidate,
  });
}

export function useDeleteTag() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrapEmpty(await api.DELETE("/tags/{tag_id}", { params: { path: { tag_id: id } } }));
    },
    onSuccess: invalidate,
  });
}

export function useTagPapers() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async ({
      id,
      paperIds,
      remove = false,
    }: {
      id: string;
      paperIds: string[];
      remove?: boolean;
    }) => {
      const params = { path: { tag_id: id } };
      const body = { paper_ids: paperIds };
      return unwrap(
        remove
          ? await api.POST("/tags/{tag_id}/papers/remove", { params, body })
          : await api.POST("/tags/{tag_id}/papers", { params, body }),
      );
    },
    onSuccess: invalidate,
  });
}

export function useSetReadingStatus() {
  const api = useApi();
  const invalidate = useInvalidateLibrary();
  return useMutation({
    mutationFn: async (body: { paper_ids: string[]; reading_status: ReadingStatus }) =>
      unwrap(await api.PATCH("/papers/reading-status", { body })),
    onSuccess: invalidate,
  });
}
