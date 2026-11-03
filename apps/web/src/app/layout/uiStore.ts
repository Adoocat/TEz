// Panel layout, remembered per user on this device (design-prompt §3).
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

interface LayoutState {
  sidebarOpen: boolean;
  inspectorOpen: boolean;
  toggleSidebar: () => void;
  toggleInspector: () => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      inspectorOpen: true,
      toggleSidebar: () => {
        set((s) => ({ sidebarOpen: !s.sidebarOpen }));
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
