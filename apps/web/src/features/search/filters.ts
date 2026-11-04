// Filters on results already fetched. Only the year goes to the sources, because type,
// language and open access are recorded unevenly and asking for them would hide papers.
import type { components } from "@/api/schema";

import type { SearchResultRow } from "./api";

export type VenueType = components["schemas"]["VenueType"];

export interface ResultFilters {
  venueType: VenueType | null;
  language: string | null;
  openAccessOnly: boolean;
}

export const noFilters: ResultFilters = { venueType: null, language: null, openAccessOnly: false };

export function filterRows(rows: SearchResultRow[], filters: ResultFilters): SearchResultRow[] {
  return rows.filter(
    (row) =>
      (filters.venueType === null || row.venue_type === filters.venueType) &&
      (filters.language === null || row.language === filters.language) &&
      (!filters.openAccessOnly || row.oa_url !== null),
  );
}

/** The types and languages present, so the menus offer only what would match something. */
export function availableOptions(rows: SearchResultRow[]) {
  const venueTypes = new Set<VenueType>();
  const languages = new Set<string>();
  for (const row of rows) {
    if (row.venue_type) venueTypes.add(row.venue_type);
    if (row.language) languages.add(row.language);
  }
  return { venueTypes: [...venueTypes].sort(), languages: [...languages].sort() };
}

/** How a row's duplicates were recognized: the methods, without the row's first sighting. */
export function mergeReasons(row: SearchResultRow): { method: string; score: number | null }[] {
  return row.sources
    .filter((source) => source.match_method !== "new")
    .map((source) => ({ method: source.match_method, score: source.match_score }));
}
