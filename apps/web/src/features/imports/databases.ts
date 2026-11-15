// Databases without an open API: their results come in as export files (ADR 0019). Each has
// the address of its search page, for "Open site" (Task 27), and a short export guide
// (Task 26, `search.external.guides.<key>`). Which of them has a tested import preset comes
// from the backend (GET /imports/presets).

export interface Database {
  key: string;
  // As the import logs it in `search_run.source`; the backend's preset uses the same name.
  name: string;
  site: string | null;
}

export const databases: readonly Database[] = [
  {
    key: "wos",
    name: "Web of Science",
    site: "https://www.webofscience.com/wos/woscc/advanced-search",
  },
  { key: "scopus", name: "Scopus", site: "https://www.scopus.com/search/form.uri" },
  { key: "jstor", name: "JSTOR", site: "https://www.jstor.org/action/showAdvancedSearch" },
  { key: "ebsco", name: "EBSCO", site: "https://search.ebscohost.com/" },
  { key: "proquest", name: "ProQuest", site: "https://www.proquest.com/" },
  // Reached through the library's host (EBSCO, ProQuest, Ovid): no single address.
  { key: "psycinfo", name: "APA PsycInfo", site: null },
  { key: "ieee", name: "IEEE Xplore", site: "https://ieeexplore.ieee.org/search/advanced" },
  { key: "acm", name: "ACM DL", site: "https://dl.acm.org/search/advanced" },
  { key: "scholar", name: "Google Scholar", site: "https://scholar.google.com/" },
  { key: "trdizin", name: "TR Dizin", site: "https://search.trdizin.gov.tr/" },
  { key: "yoktez", name: "YÖK Tez", site: "https://tez.yok.gov.tr/UlusalTezMerkezi/" },
];

/** Names offered in the database menus; anything else is typed in. */
export const knownDatabases = databases.map((database) => database.name);
export const defaultDatabase = "Web of Science";

export function databaseNamed(name: string): Database | null {
  return databases.find((database) => database.name === name) ?? null;
}

/** The database's search page, or null for one TEz does not know. */
export function databaseSite(name: string): string | null {
  return databaseNamed(name)?.site ?? null;
}
