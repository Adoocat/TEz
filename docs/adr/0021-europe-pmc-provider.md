# 0021 — Europe PMC as a search source

- **Status:** Accepted
- **Date:** 2026-11-15
- **Task:** 29 (second of two PRs; PubMed is ADR 0020)

## Context

Europe PMC holds PubMed's records plus preprints, agricultural literature, theses and full texts from PubMed Central and its European mirrors. With PubMed (ADR 0020) it covers health, psychology, life sciences and education reviews that OpenAlex alone reaches less precisely. CLAUDE.md rule 1 limits network access to a named list; the owner approved Europe PMC on 2026-11-15.

What we checked (2026-11-15). The documentation page (europepmc.org/RestfulWebService) refuses non-browser clients, so the facts below come from the Europe PMC team's answers on its web-services forum and were confirmed with one live call:

- **Access:** `https://www.ebi.ac.uk/europepmc/webservices/rest/search`, free, no key or account.
- **Paging:** `pageSize` up to 1000; deep paging only with `cursorMark` (`*` first, then each answer's `nextCursorMark`).
- **Rate limit:** about 10 requests a second per IP; 429 above it. No daily cap stated.
- **Query syntax:** `AND`/`OR`/`NOT`, quotes, parentheses; fields as `FIELD:term` (`MESH`, `TITLE`, `TITLE_ABS`, `AUTH`, `JOURNAL`, `PUB_YEAR:[a TO b]`). `TITLE_ABS` and `AUTH` were checked live.
- **Terms:** EMBL-EBI places no restrictions beyond those of the original data owners; the Europe PMC team allows the APIs in commercial services. Record licences vary; TEz keeps metadata and abstracts in the user's own library as with every other source.

## Decision

- A `EuropePmcProvider` behind `PagedProvider` (ADR 0008): one call per page, `format=json`, `resultType=core`, 500 records per page, cursor paging; `email` only when the user set a contact address.
- Policy: 5 requests a second, half the stated limit, because labs and campuses share one IP.
- Query translation reuses PubMed's field-tag reading: a PubMed tag becomes the Europe PMC field (`"Neoplasms"[MeSH]` → `MESH:"Neoplasms"`, `[tiab]` → `TITLE_ABS:`, `[au]` → `AUTH:`, `[ta]` → `JOURNAL:`); an unknown tag is dropped and its term searched as is. Years are added as `AND PUB_YEAR:[from TO to]` and are part of the recorded query.
- Mapping: PMID, PMCID, DOI; `<h4>` abstract sections become labels; collective authors, ORCID, first affiliation; source `PPR` is a preprint; publication types for conference, report, book, chapter and thesis; `Retracted Publication`; an open-access PDF link becomes `oa_url`; `citedByCount`. The record's Europe PMC page is its URL.
- Europe PMC's PubMed records merge with PubMed's through the PMID and PMCID identifiers from ADR 0020.
- Source chip (on by default), `tez search --sources europepmc` (alias `epmc`), CLAUDE.md rule 1 lists Europe PMC.

## Consequences

- Searching both PubMed and Europe PMC finds many records twice; deduplication merges them by identifier, and PRISMA counts the duplicates per source as usual.
- Full-text search (Europe PMC can search inside open-access full texts) is not used: a systematic search over metadata and abstracts is what reports describe. It can be offered later as an explicit option.
