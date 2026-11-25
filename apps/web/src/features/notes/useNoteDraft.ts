// A note being written: saved a moment after each change, and kept on this device until the save
// is confirmed, so closing the window loses nothing.
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/query";

import { useSaveNote, type NoteView } from "./api";

const SAVE_AFTER_MS = 700;

export type SaveState = "saved" | "dirty" | "saving" | "failed" | "conflict";

interface Draft {
  title: string;
  body: string;
  /** The version the text is based on. */
  version: number;
}

const draftKey = (id: string) => `tez.note.draft.${id}`;

export function readDraft(id: string): Draft | null {
  try {
    const text = localStorage.getItem(draftKey(id));
    const draft = text === null ? null : (JSON.parse(text) as Partial<Draft>);
    if (
      typeof draft?.title === "string" &&
      typeof draft.body === "string" &&
      typeof draft.version === "number"
    ) {
      return { title: draft.title, body: draft.body, version: draft.version };
    }
  } catch {
    console.warn("an unreadable note draft was dropped");
  }
  return null;
}

function writeDraft(id: string, draft: Draft | null) {
  if (draft) localStorage.setItem(draftKey(id), JSON.stringify(draft));
  else localStorage.removeItem(draftKey(id));
}

export function useNoteDraft(note: NoteView) {
  const save = useSaveNote(note.id);
  // A draft left by a closed window. Based on another version than the saved one, it waits for
  // the user: both texts may hold work.
  const [left] = useState(() => {
    const draft = readDraft(note.id);
    return draft && (draft.title !== note.title || draft.body !== note.body) ? draft : null;
  });
  const recovered = left !== null && left.version === note.version;
  const [title, setTitle] = useState(recovered ? left.title : note.title);
  const [body, setBody] = useState(recovered ? left.body : note.body);
  const [state, setState] = useState<SaveState>(
    left === null ? "saved" : recovered ? "dirty" : "conflict",
  );
  // What a save needs, readable after the component is gone.
  const now = useRef({ title, body, version: note.version, state });
  const saving = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const { mutateAsync } = save;

  const set = useCallback((next: SaveState) => {
    now.current.state = next;
    setState(next);
  }, []);

  // A save that finds newer text saves once more.
  const again = useRef<() => Promise<void>>(() => Promise.resolve());
  const flush = useCallback(
    async ({ overwrite = false } = {}) => {
      clearTimeout(timer.current);
      if (saving.current) return;
      if (!overwrite && now.current.state !== "dirty" && now.current.state !== "failed") return;
      const sent = { title: now.current.title.trim(), body: now.current.body };
      saving.current = true;
      set("saving");
      try {
        const saved = await mutateAsync({
          // A note without a title keeps the one it had.
          ...(sent.title ? { title: sent.title } : {}),
          body: sent.body,
          ...(overwrite ? {} : { base_version: now.current.version }),
        });
        now.current.version = saved.version;
        const changed = now.current.body !== sent.body || now.current.title.trim() !== sent.title;
        if (changed) {
          set("dirty");
          timer.current = setTimeout(() => void again.current(), SAVE_AFTER_MS);
        } else {
          writeDraft(note.id, null);
          set("saved");
        }
      } catch (error) {
        set(error instanceof ApiError && error.code === "note.conflict" ? "conflict" : "failed");
      } finally {
        saving.current = false;
      }
    },
    [mutateAsync, note.id, set],
  );

  const changed = useCallback(() => {
    const { title: t, body: b, version } = now.current;
    writeDraft(note.id, { title: t, body: b, version });
    // In a conflict nothing is saved until the user has chosen.
    if (now.current.state === "conflict") return;
    if (now.current.state !== "saving") set("dirty");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => void flush(), SAVE_AFTER_MS);
  }, [flush, note.id, set]);

  useEffect(() => {
    again.current = flush;
  }, [flush]);

  // Leaving the note saves at once; so does hiding the window.
  useEffect(() => {
    const onHide = () => void flush();
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", onHide);
    if (now.current.state === "dirty") timer.current = setTimeout(() => void flush(), 0);
    return () => {
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("pagehide", onHide);
      void flush();
    };
  }, [flush]);

  return {
    title,
    body,
    state,
    /** A draft from a closed window that does not fit the saved note any more. */
    left: state === "conflict" ? left : null,
    setTitle: (next: string) => {
      now.current.title = next;
      setTitle(next);
      changed();
    },
    setBody: (next: string) => {
      now.current.body = next;
      setBody(next);
      changed();
    },
    retry: () => void flush(),
    /** Conflict: this text wins. */
    keepMine: async () => {
      if (left && now.current.body === note.body && now.current.title === note.title) {
        now.current.title = left.title;
        now.current.body = left.body;
      }
      await flush({ overwrite: true });
    },
    /** Into another note, or to the top. */
    moveTo: async (parentId: string | null) => {
      await flush();
      const saved = await mutateAsync({ parent_id: parentId });
      now.current.version = saved.version;
    },
    /** Conflict: the saved text wins; the caller loads the note again. */
    dropMine: () => {
      clearTimeout(timer.current);
      writeDraft(note.id, null);
      now.current.state = "saved";
    },
  };
}
