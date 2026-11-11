// The library list's filters (design 4.3: year, reading status, tag, PDF). They run on the
// loaded rows: a library holds a few thousand papers, so this is instant. Text search is the
// backend's (FTS); its hits arrive as ids and narrow the rows like any other filter.
import type { LibraryPaperRow, ReadingStatus } from "./api";

export type PdfFilter = "any" | "has" | "none";

export interface LibraryFilters {
  yearFrom: number | null;
  yearTo: number | null;
  reading: ReadingStatus | null;
  tagId: string | null;
  pdf: PdfFilter;
}

export const noLibraryFilters: LibraryFilters = {
  yearFrom: null,
  yearTo: null,
  reading: null,
  tagId: null,
  pdf: "any",
};

export function isFiltered(filters: LibraryFilters): boolean {
  return (
    filters.yearFrom !== null ||
    filters.yearTo !== null ||
    filters.reading !== null ||
    filters.tagId !== null ||
    filters.pdf !== "any"
  );
}

/**
 * Rows that pass the filters. With `hits` (search results, best first), only those rows,
 * in that order.
 */
export function applyFilters(
  rows: LibraryPaperRow[],
  filters: LibraryFilters,
  hits: string[] | null,
): LibraryPaperRow[] {
  const keep = (row: LibraryPaperRow) =>
    (filters.yearFrom === null || (row.year !== null && row.year >= filters.yearFrom)) &&
    (filters.yearTo === null || (row.year !== null && row.year <= filters.yearTo)) &&
    (filters.reading === null || row.reading_status === filters.reading) &&
    (filters.tagId === null || row.tag_ids.includes(filters.tagId)) &&
    (filters.pdf === "any" || (filters.pdf === "has") === (row.pdf !== "none"));
  if (hits === null) return rows.filter(keep);
  const byId = new Map(rows.map((row) => [row.id, row]));
  return hits.flatMap((id) => {
    const row = byId.get(id);
    return row && keep(row) ? [row] : [];
  });
}
