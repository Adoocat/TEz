// Publication types as filters and labels show them (Task 28): the venue type, with a thesis
// split by degree when the source said which.
import type { components } from "@/api/schema";

export type VenueType = components["schemas"]["VenueType"];
export type ThesisType = components["schemas"]["ThesisType"];

export type PublicationType = VenueType | `thesis_${ThesisType}`;

interface Typed {
  venue_type: VenueType | null;
  thesis_type: ThesisType | null;
}

/** Every type a filter can offer, theses by degree right after "thesis". */
export const publicationTypes: PublicationType[] = [
  "journal",
  "conference",
  "preprint",
  "book",
  "chapter",
  "thesis",
  "thesis_masters",
  "thesis_doctoral",
  "report",
  "other",
];

/** A "thesis" filter keeps every thesis; a degree keeps only those of that degree. */
export function hasPublicationType(row: Typed, type: PublicationType): boolean {
  if (type === "thesis_masters" || type === "thesis_doctoral") {
    return row.venue_type === "thesis" && `thesis_${row.thesis_type ?? ""}` === type;
  }
  return row.venue_type === type;
}

/** The most precise type of a row, for its label: "Thesis (doctoral)" over "Thesis". */
export function publicationTypeOf(row: Typed): PublicationType | null {
  if (row.venue_type === "thesis" && row.thesis_type) return `thesis_${row.thesis_type}`;
  return row.venue_type;
}

/** The types present in rows, in menu order (a degree also offers plain "thesis"). */
export function presentTypes(rows: Typed[]): PublicationType[] {
  return publicationTypes.filter((type) => rows.some((row) => hasPublicationType(row, type)));
}
