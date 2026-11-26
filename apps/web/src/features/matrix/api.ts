// The literature matrix (Tasks 51–52): matrices, columns, cells.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

export type MatrixView = components["schemas"]["MatrixView"];
export type MatrixSummary = components["schemas"]["MatrixSummary"];
export type ColumnView = components["schemas"]["ColumnView"];
export type ColumnCreate = components["schemas"]["ColumnCreate"];
export type ColumnPatch = components["schemas"]["ColumnPatch"];
export type RowView = components["schemas"]["RowView"];
export type CellView = components["schemas"]["CellView"];
export type TypeChange = components["schemas"]["TypeChange"];
export type TypeChangeReport = components["schemas"]["TypeChangeReport"];
export type DataType = ColumnView["data_type"];
export type CellValue = CellView["value"];

export const matrixKeys = {
  list: (reviewId: string) => ["reviews", reviewId, "matrices"] as const,
  one: (matrixId: string) => ["matrices", matrixId] as const,
};

export function useMatrices(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: matrixKeys.list(reviewId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/matrices", {
          params: { path: { review_id: reviewId } },
        }),
      ),
  });
}

export function useMatrix(matrixId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: matrixKeys.one(matrixId ?? ""),
    enabled: matrixId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/matrices/{matrix_id}", {
          params: { path: { matrix_id: matrixId ?? "" } },
        }),
      ),
  });
}

export function useCreateMatrix(reviewId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (name: string) =>
      unwrap(
        await api.POST("/reviews/{review_id}/matrices", {
          params: { path: { review_id: reviewId } },
          body: { name },
        }),
      ),
    onSuccess: (matrix) => {
      queryClient.setQueryData(matrixKeys.one(matrix.id), matrix);
      return queryClient.invalidateQueries({ queryKey: matrixKeys.list(reviewId) });
    },
  });
}

/** Column changes reload the matrix: a type change touches every cell of the column. */
function useReload(matrixId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: matrixKeys.one(matrixId) });
}

const matrixPath = (matrixId: string) => ({ params: { path: { matrix_id: matrixId } } });
const columnPath = (matrixId: string, columnId: string) => ({
  params: { path: { matrix_id: matrixId, column_id: columnId } },
});

export function useAddColumn(matrixId: string) {
  const api = useApi();
  const reload = useReload(matrixId);
  return useMutation({
    mutationFn: async (body: ColumnCreate) =>
      unwrap(await api.POST("/matrices/{matrix_id}/columns", { ...matrixPath(matrixId), body })),
    onSuccess: reload,
  });
}

export function useUpdateColumn(matrixId: string) {
  const api = useApi();
  const reload = useReload(matrixId);
  return useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: ColumnPatch }) =>
      unwrap(
        await api.PATCH("/matrices/{matrix_id}/columns/{column_id}", {
          ...columnPath(matrixId, id),
          body: patch,
        }),
      ),
    onSuccess: reload,
  });
}

/** A new type or new options; with `dry_run` only the report of what would happen. */
export function useChangeType(matrixId: string) {
  const api = useApi();
  const reload = useReload(matrixId);
  return useMutation({
    mutationFn: async ({ id, change }: { id: string; change: TypeChange }) =>
      unwrap(
        await api.PUT("/matrices/{matrix_id}/columns/{column_id}/type", {
          ...columnPath(matrixId, id),
          body: change,
        }),
      ),
    onSuccess: async (report) => {
      if (report.applied) await reload();
    },
  });
}

export function useDeleteColumn(matrixId: string) {
  const api = useApi();
  const reload = useReload(matrixId);
  return useMutation({
    mutationFn: async (id: string) => {
      unwrapEmpty(
        await api.DELETE("/matrices/{matrix_id}/columns/{column_id}", columnPath(matrixId, id)),
      );
    },
    onSuccess: reload,
  });
}

export function useReorderColumns(matrixId: string) {
  const api = useApi();
  const reload = useReload(matrixId);
  return useMutation({
    mutationFn: async (columnIds: string[]) =>
      unwrap(
        await api.PUT("/matrices/{matrix_id}/columns/order", {
          ...matrixPath(matrixId),
          body: { column_ids: columnIds },
        }),
      ),
    onSuccess: reload,
  });
}

export interface CellWrite {
  paperId: string;
  columnId: string;
  value: CellValue;
  /** With a null value: text a type change kept, put back by undo. */
  keptText?: string | null;
}

/** Writes a cell. The grid shows the new value at once; a failed write puts the old one back. */
export function usePutCell(matrixId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  const key = matrixKeys.one(matrixId);
  return useMutation({
    mutationFn: async ({ paperId, columnId, value, keptText }: CellWrite) =>
      unwrap(
        await api.PUT("/matrices/{matrix_id}/cells/{paper_id}/{column_id}", {
          params: { path: { matrix_id: matrixId, paper_id: paperId, column_id: columnId } },
          body: { value, kept_text: keptText ?? null },
        }),
      ),
    onMutate: async (write) => {
      await queryClient.cancelQueries({ queryKey: key });
      const before = queryClient.getQueryData<MatrixView>(key);
      if (before) queryClient.setQueryData(key, withCell(before, write));
      return { before };
    },
    onError: (_error, _write, context) => {
      if (context?.before) queryClient.setQueryData(key, context.before);
    },
    onSuccess: (cell, write) => {
      queryClient.setQueryData<MatrixView>(key, (now) => (now ? withCell(now, write, cell) : now));
    },
  });
}

function withCell(matrix: MatrixView, write: CellWrite, saved?: CellView | null): MatrixView {
  const empty = write.value === null && !write.keptText;
  const cell: CellView | null =
    saved !== undefined
      ? saved
      : empty
        ? null
        : {
            column_id: write.columnId,
            value: write.value,
            kept_text: write.value === null ? (write.keptText ?? null) : null,
            origin: "manual",
            updated_at: new Date().toISOString(),
          };
  return {
    ...matrix,
    rows: matrix.rows.map((row) =>
      row.paper_id !== write.paperId
        ? row
        : {
            ...row,
            cells: [
              ...row.cells.filter((c) => c.column_id !== write.columnId),
              ...(cell ? [cell] : []),
            ],
          },
    ),
  };
}

/** A cell's content as it was, for undo. */
export function snapshotOf(cell: CellView | undefined): {
  value: CellValue;
  keptText: string | null;
} {
  return { value: cell?.value ?? null, keptText: cell?.kept_text ?? null };
}
