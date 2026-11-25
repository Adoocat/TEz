// The reader's open documents, as tabs, remembered on this device (design 4.5).
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export interface ReaderTab {
  attachmentId: string;
  title: string;
  /** The page last read, so a tab opens where it was left. */
  page: number;
}

interface ReaderTabs {
  tabs: ReaderTab[];
  activeId: string | null;
  /** Adds the tab, or fronts it and refreshes its title. */
  open: (attachmentId: string, title: string) => void;
  setPage: (attachmentId: string, page: number) => void;
  /** Closes a tab and says which one to show instead (null: none left). */
  close: (attachmentId: string) => ReaderTab | null;
}

export const useReaderTabs = create<ReaderTabs>()(
  persist(
    (set, get) => ({
      tabs: [],
      activeId: null,
      open: (attachmentId, title) => {
        set(({ tabs }) => ({
          activeId: attachmentId,
          tabs: tabs.some((tab) => tab.attachmentId === attachmentId)
            ? tabs.map((tab) => (tab.attachmentId === attachmentId ? { ...tab, title } : tab))
            : [...tabs, { attachmentId, title, page: 1 }],
        }));
      },
      setPage: (attachmentId, page) => {
        set(({ tabs }) => ({
          tabs: tabs.map((tab) => (tab.attachmentId === attachmentId ? { ...tab, page } : tab)),
        }));
      },
      close: (attachmentId) => {
        const { tabs, activeId } = get();
        const index = tabs.findIndex((tab) => tab.attachmentId === attachmentId);
        const rest = tabs.filter((tab) => tab.attachmentId !== attachmentId);
        const next =
          activeId === attachmentId
            ? (rest[Math.min(Math.max(index, 0), rest.length - 1)] ?? null)
            : (rest.find((tab) => tab.attachmentId === activeId) ?? null);
        set({ tabs: rest, activeId: next?.attachmentId ?? null });
        return next;
      },
    }),
    {
      name: "tez.reader",
      storage: createJSONStorage(() => localStorage),
      partialize: ({ tabs, activeId }) => ({ tabs, activeId }),
    },
  ),
);

interface ReaderPanel {
  open: boolean;
  tab: "outline" | "pages";
  toggle: () => void;
  setTab: (tab: "outline" | "pages") => void;
}

/** The panel left of the document: its outline, or small pictures of its pages. */
export const useReaderPanel = create<ReaderPanel>()(
  persist(
    (set) => ({
      open: false,
      tab: "outline",
      toggle: () => {
        set((state) => ({ open: !state.open }));
      },
      setTab: (tab) => {
        set({ tab });
      },
    }),
    { name: "tez.reader.panel", storage: createJSONStorage(() => localStorage) },
  ),
);
