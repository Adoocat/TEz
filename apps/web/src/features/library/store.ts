import { create } from "zustand";

import type { PaperScope } from "./api";

interface LibraryView {
  scope: PaperScope;
  /** The paper shown in the inspector. */
  selectedPaperId: string | null;
  setScope: (scope: PaperScope) => void;
  selectPaper: (paperId: string | null) => void;
}

export const useLibraryView = create<LibraryView>((set) => ({
  scope: { kind: "all" },
  selectedPaperId: null,
  setScope: (scope) => {
    set({ scope, selectedPaperId: null });
  },
  selectPaper: (paperId) => {
    set({ selectedPaperId: paperId });
  },
}));
