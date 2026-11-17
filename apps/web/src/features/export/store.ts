// What the export screen remembers between visits: the papers chosen in the library (the
// "selected" scope) and the last format, style and language.
import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { CslLocale, CslStyle } from "./api";

export type ExportFormat = "bibliography" | "bibtex" | "ris";

export type ScopeKind = "included" | "selected" | "collection" | "library";

interface ExportChoices {
  format: ExportFormat;
  style: CslStyle;
  locale: CslLocale | null;
  setFormat: (format: ExportFormat) => void;
  setStyle: (style: CslStyle) => void;
  setLocale: (locale: CslLocale) => void;
}

/** Kept on this device, like the other screens' view choices. */
export const useExportChoices = create<ExportChoices>()(
  persist(
    (set) => ({
      format: "bibliography",
      style: "apa",
      locale: null,
      setFormat: (format) => {
        set({ format });
      },
      setStyle: (style) => {
        set({ style });
      },
      setLocale: (locale) => {
        set({ locale });
      },
    }),
    {
      name: "tez.export",
      partialize: ({ format, style, locale }) => ({ format, style, locale }),
    },
  ),
);

interface ExportSelection {
  /** Papers chosen in the library; the export screen offers them as a scope. */
  paperIds: string[];
  choose: (paperIds: string[]) => void;
}

export const useExportSelection = create<ExportSelection>((set) => ({
  paperIds: [],
  choose: (paperIds) => {
    set({ paperIds });
  },
}));
