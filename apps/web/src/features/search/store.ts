// What the search screen is looking at. Kept outside the page so it survives moving to
// another section and back; the data itself stays in TanStack Query.
import { create } from "zustand";

interface SearchViewState {
  activeSearchId: string | null;
  selectedPaperId: string | null;
  openSearch: (searchId: string) => void;
  selectPaper: (paperId: string | null) => void;
}

export const useSearchView = create<SearchViewState>()((set) => ({
  activeSearchId: null,
  selectedPaperId: null,
  openSearch: (searchId) => {
    set({ activeSearchId: searchId, selectedPaperId: null });
  },
  selectPaper: (paperId) => {
    set({ selectedPaperId: paperId });
  },
}));
