import { create } from "zustand";

/** One dropped file and what became of it, for the notices in the corner. */
export interface UploadNotice {
  id: number;
  fileName: string;
  state: "uploading" | "added" | "duplicate" | "failed";
  /** For failed: the backend's error code (an i18n key under errors.). */
  errorCode?: string;
  errorParams?: Record<string, unknown>;
}

interface UploadState {
  notices: UploadNotice[];
  start: (fileName: string) => number;
  update: (id: number, change: Partial<Omit<UploadNotice, "id">>) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useUploadStore = create<UploadState>((set) => ({
  notices: [],
  start(fileName) {
    const id = nextId++;
    set((state) => ({ notices: [...state.notices, { id, fileName, state: "uploading" }] }));
    return id;
  },
  update(id, change) {
    set((state) => ({
      notices: state.notices.map((notice) =>
        notice.id === id ? { ...notice, ...change } : notice,
      ),
    }));
  },
  dismiss(id) {
    set((state) => ({ notices: state.notices.filter((notice) => notice.id !== id) }));
  },
}));
