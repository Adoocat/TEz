import { create } from "zustand";

interface OpenState {
  /** A .bib/.ris file to open in the import dialog (from `tez refs.bib` or "Open with"). */
  importPath: string | null;
  setImportPath: (path: string | null) => void;
}

export const useOpenStore = create<OpenState>((set) => ({
  importPath: null,
  setImportPath: (importPath) => {
    set({ importPath });
  },
}));
