import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type Mode = "edit" | "both" | "preview";

interface NoteMode {
  mode: Mode;
  setMode: (mode: Mode) => void;
}

/** How notes are shown, remembered on this device. */
export const useNoteMode = create<NoteMode>()(
  persist(
    (set) => ({
      mode: "both",
      setMode: (mode) => {
        set({ mode });
      },
    }),
    { name: "tez.notes", storage: createJSONStorage(() => localStorage) },
  ),
);
