import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

export type NoteSummary = components["schemas"]["NoteSummary"];
export type NoteView = components["schemas"]["NoteView"];
export type NoteLinkView = components["schemas"]["NoteLinkView"];
export type LinkSuggestion = components["schemas"]["LinkSuggestion"];
export type Backlink = components["schemas"]["Backlink"];

export const noteKeys = {
  all: ["notes"] as const,
  list: ["notes", "list"] as const,
  note: (id: string) => ["notes", "note", id] as const,
  backlinks: (id: string) => ["notes", "backlinks", id] as const,
  ofPaper: (id: string) => ["notes", "paper", id] as const,
};

export function useNotes() {
  const api = useApi();
  return useQuery({
    queryKey: noteKeys.list,
    queryFn: async () => unwrap(await api.GET("/notes")),
  });
}

export function useNote(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: noteKeys.note(id),
    // The editor starts from this text: never from an old copy.
    gcTime: 0,
    queryFn: async () =>
      unwrap(await api.GET("/notes/{note_id}", { params: { path: { note_id: id } } })),
  });
}

export function useNoteSearch(query: string) {
  const api = useApi();
  const q = query.trim();
  return useQuery({
    queryKey: ["notes", "search", q] as const,
    enabled: q !== "",
    placeholderData: (previous) => previous,
    queryFn: async () => unwrap(await api.GET("/notes/search", { params: { query: { q } } })),
  });
}

export function useBacklinks(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: noteKeys.backlinks(id),
    queryFn: async () =>
      unwrap(await api.GET("/notes/{note_id}/backlinks", { params: { path: { note_id: id } } })),
  });
}

export function usePaperNotes(paperId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: noteKeys.ofPaper(paperId ?? ""),
    enabled: paperId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/papers/{paper_id}/notes", {
          params: { path: { paper_id: paperId ?? "" } },
        }),
      ),
  });
}

/** For the editor's `[[`: asked for while typing, outside React's rendering. */
export function useLinkSuggestions() {
  const api = useApi();
  return async (q: string) => unwrap(await api.GET("/notes/suggest", { params: { query: { q } } }));
}

export function useCreateNote() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      title: string;
      body?: string;
      parent_id?: string | null;
      paper_id?: string | null;
      review_id?: string | null;
    }) => unwrap(await api.POST("/notes", { body: { body: "", ...body } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: noteKeys.all }),
  });
}

export interface NoteChanges {
  title?: string;
  body?: string;
  parent_id?: string | null;
  base_version?: number;
}

export function useSaveNote(id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (changes: NoteChanges) =>
      unwrap(
        await api.PATCH("/notes/{note_id}", {
          params: { path: { note_id: id } },
          body: changes,
        }),
      ),
    onSuccess: async (note) => {
      // A reading that started before this save would bring the old text back.
      await queryClient.cancelQueries({ queryKey: noteKeys.note(id) });
      queryClient.setQueryData(noteKeys.note(id), note);
      await queryClient.invalidateQueries({ queryKey: noteKeys.list });
      await queryClient.invalidateQueries({ queryKey: ["notes", "backlinks"] });
      await queryClient.invalidateQueries({ queryKey: ["notes", "paper"] });
      await queryClient.invalidateQueries({ queryKey: ["notes", "search"] });
    },
  });
}

export function useAppendToNote() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, text }: { id: string; text: string }) =>
      unwrap(
        await api.POST("/notes/{note_id}/append", {
          params: { path: { note_id: id } },
          body: { text },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: noteKeys.all }),
  });
}

export function useDeleteNote() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrapEmpty(await api.DELETE("/notes/{note_id}", { params: { path: { note_id: id } } }));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: noteKeys.list }),
  });
}

export function useRestoreNote() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.POST("/notes/{note_id}/restore", { params: { path: { note_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: noteKeys.all }),
  });
}

/** Where an anchor link goes; its note may not know yet (just typed). */
export function useAnchorAddress() {
  const api = useApi();
  return async (anchorId: string) => {
    const anchor = unwrap(
      await api.GET("/anchors/{anchor_id}", { params: { path: { anchor_id: anchorId } } }),
    );
    return `/reader/${anchor.attachment_id}?anchor=${anchor.id}`;
  };
}
