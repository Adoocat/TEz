// The cell the matrix grid has active, for the panel beside it (Task 53).
import { create } from "zustand";

export interface ActiveCell {
  matrixId: string;
  paperId: string;
  columnId: string;
}

interface MatrixSelection {
  cell: ActiveCell | null;
  setCell: (cell: ActiveCell | null) => void;
}

export const useMatrixSelection = create<MatrixSelection>((set) => ({
  cell: null,
  setCell: (cell) => {
    set({ cell });
  },
}));

/** Where a cell is shown in the matrix: the address the reader's Matrix tab links to. */
export function matrixCellPath({ matrixId, paperId, columnId }: ActiveCell): string {
  const params = new URLSearchParams({ matrix: matrixId, paper: paperId, column: columnId });
  return `/matrix?${params.toString()}`;
}
