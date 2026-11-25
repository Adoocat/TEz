// Panel layout, remembered per user on this device (design-prompt §3).
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface LayoutState {
  sidebarOpen: boolean;
  inspectorOpen: boolean;
  /** Focus mode (reader): everything but the document is hidden. Not remembered. */
  focus: boolean;
  setFocus: (focus: boolean) => void;
  toggleSidebar: () => void;
  toggleInspector: () => void;
  openInspector: () => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      inspectorOpen: true,
      focus: false,
      setFocus: (focus) => {
        set({ focus });
      },
      toggleSidebar: () => {
        set((s) => ({ sidebarOpen: !s.sidebarOpen }));
      },
      openInspector: () => {
        set({ inspectorOpen: true });
      },
      toggleInspector: () => {
        set((s) => ({ inspectorOpen: !s.inspectorOpen }));
      },
    }),
    {
      name: "tez.layout",
      storage: createJSONStorage(() => localStorage),
      partialize: ({ sidebarOpen, inspectorOpen }) => ({ sidebarOpen, inspectorOpen }),
    },
  ),
);
