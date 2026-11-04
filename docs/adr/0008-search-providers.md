# 0008 — Search providers: results instead of exceptions, one query per dialect

- **Status:** Accepted
- **Date:** 2026-11-04
- **Task:** 11 (providers)

## Context

Task 11 maps OpenAlex, Semantic Scholar, arXiv and Crossref to `NormalizedRecord`, tested against recorded real responses. The owner also asked for DBLP as a fifth provider (open question 3). The plan says each source's current documentation is checked before it is written. That check, and live requests, changed several assumptions.

## Decision

- **`search` does not raise for a source's failure.** It returns a `ProviderResult` with what arrived and the error; its status is `ok`, `partial` or `error`. Task 13 needs exactly this to record a failed source and continue with the others.
- **One user query, translated per source** (`providers/query.py`). The translation is what is stored on `search_run.translated_query`. Parsing never fails: unbalanced parentheses and dangling operators are dropped.
- **A `NOT` with no left side is dropped with its operand,** for sources that cannot express it. Searching for the operand would return the opposite of what the user asked. A query left empty is not sent (`source.query_unsupported`).
- **OpenAlex:** `mailto` no longer exists. The key goes in `Authorization: Bearer`. Without a key:
  - cursor paging stops after the first page (401) and a page holds at most 100 results;
  - one small daily budget is shared per IP address;
  - search can be paused with 429 under load.

  The provider therefore stops after one page without a key and reports `source.key_required`, so the run is `partial`.
- **Semantic Scholar:** bulk search, the only endpoint with boolean syntax and full-corpus paging. It ignores `limit`; the shared loop cuts the page. Keyless requests share one pool and often get 429.
- **arXiv:** one request per three seconds, as the API asks. Year limits become part of the query.
- **Crossref:** `query.bibliographic` has no boolean logic, so the translated query is plain words and results are broad. `sort=score` keeps cursor paging ranked. Crossref's PDF links are not treated as open access, because many are paywalled.
- **DBLP is postponed** *(owner's decision)*. `dblp.org` answers API requests with an Anubis bot-check page (HTTP 202, HTML). We do not try to get past such a check, so the app cannot use the API and no real response can be recorded. Its chip stays hidden. It can come back if dblp allows API clients or removes the check. Semantic Scholar still supplies DBLP identifiers.
- **Cassettes** live in `tests/cassettes/<source>/`. Keys, e-mail addresses and the user agent are filtered out. Rate-limit responses from recording runs are removed, and the Semantic Scholar cassette is cut to five records, because that source sends every match.

## Consequences

- Real use really needs free keys for OpenAlex and Semantic Scholar. Without them a search gets at most 100 OpenAlex results and may lose Semantic Scholar to 429. The UI should say so (Task 14).
- Cursor paging with an OpenAlex key has not been recorded, because no key was available. `test_base.py` covers the loop, and the first real use with a key should confirm it.
- The bundled expat protects `xml.etree` against entity expansion; `defusedxml` was not added.
- New development dependencies: `pytest-recording` (MIT), `vcrpy` (MIT), `wrapt` (BSD-2-Clause).
