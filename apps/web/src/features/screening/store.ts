// What this screening session did: how many decisions, and which ones undo takes back, last
// first. It lives in memory only; the decisions themselves are in the library.
import { create } from "zustand";

import type { ScreeningStage } from "./api";

export interface SessionDecision {
  reviewId: string;
  stage: ScreeningStage;
  paperId: string;
  decisionId: string;
}

interface SessionState {
  decided: number;
  done: SessionDecision[];
  /** Notes typed before the record has a decision; sent with its next decision. */
  pendingNotes: Record<string, string>;
  remember: (decision: SessionDecision) => void;
  /** The last decision this session made in the review and stage, taken off the list. */
  takeBack: (reviewId: string, stage: ScreeningStage) => SessionDecision | undefined;
  setPendingNote: (paperId: string, note: string | null) => void;
}

export const useScreeningSession = create<SessionState>()((set, get) => ({
  decided: 0,
  done: [],
  pendingNotes: {},
  remember: (decision) => {
    set((state) => ({ decided: state.decided + 1, done: [...state.done, decision] }));
  },
  takeBack: (reviewId, stage) => {
    const done = get().done;
    const index = done.findLastIndex((d) => d.reviewId === reviewId && d.stage === stage);
    if (index === -1) return undefined;
    set({ done: done.filter((_, i) => i !== index) });
    return done[index];
  },
  setPendingNote: (paperId, note) => {
    set((state) => ({
      pendingNotes: Object.fromEntries(
        [...Object.entries(state.pendingNotes).filter(([id]) => id !== paperId)].concat(
          note ? [[paperId, note]] : [],
        ),
      ),
    }));
  },
}));
