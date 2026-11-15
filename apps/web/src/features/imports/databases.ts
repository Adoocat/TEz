// Databases without an open API: their results come in as export files (ADR 0019). Each
// known one has the address of its search page, for "Open site" (Task 27).

// Databases whose exports people import most; anything else is typed in.
export const knownDatabases = ["IEEE Xplore", "ACM DL", "Scopus", "Web of Science"] as const;

const sites: Record<string, string> = {
  "IEEE Xplore": "https://ieeexplore.ieee.org/search/advanced",
  "ACM DL": "https://dl.acm.org/search/advanced",
  Scopus: "https://www.scopus.com/search/form.uri",
  "Web of Science": "https://www.webofscience.com/wos/woscc/advanced-search",
};

/** The database's search page, or null for one TEz does not know. */
export function databaseSite(name: string): string | null {
  return sites[name] ?? null;
}
