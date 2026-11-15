# 0020 — PubMed as a search source (NCBI E-utilities)

- **Status:** Accepted
- **Date:** 2026-11-15
- **Task:** 29 (first of two PRs; Europe PMC follows)

## Context

ADR 0019 opened TEz to every discipline. Health sciences, psychology and education reviews search PubMed first; the plan lists PubMed and Europe PMC as the first new API sources. CLAUDE.md rule 1 limits network access to a named list, so a new source needs the owner's approval, a check of the current terms, and this record. The owner approved PubMed and Europe PMC on 2026-11-15.

What we checked (2026-11-15):

- **Access:** NCBI E-utilities (`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`), no account needed. The documentation (NCBI Bookshelf NBK25497) sits behind a browser check, so the limits were taken from NLM's support article KA-05510 and matched against two recent secondary sources.
- **Rate limits:** up to 3 requests per second without an API key, up to 10 with one; above that the server answers 429. NCBI asks clients to send `tool` and `email`.
- **Paging:** ESearch returns at most the first 10,000 PMIDs of a query (`retstart` ≤ 9,999).
- **Terms:** PubMed citation data may be used freely; abstracts can carry publisher copyright. TEz stores them in the user's own library like any other source, which matches the existing use of OpenAlex and Crossref abstracts.

## Decision

- A `PubMedProvider` behind the existing `PagedProvider` protocol (ADR 0008). Each page is two calls: ESearch (`retmode=json`, `sort=relevance`, years as `datetype=pdat&mindate&maxdate`) for the PMIDs, then EFetch (`retmode=xml`) for their records, kept in ESearch's order. The raw ESearch JSON and EFetch XML go to the search snapshot together.
- No API key for now: the policy is 3 requests a second. `tool=TEz` always; `email` only when the user has set a contact address in Settings (the same one Crossref's polite pool uses). Cassettes drop `email`, as they already drop `mailto` and keys.
- Query translation: PubMed takes `AND`/`OR`/`NOT`, quotes and parentheses as TEz writes them. A field tag after a term or phrase stays attached (`"Neoplasms"[MeSH]`, `asthma [tiab]` → `asthma[tiab]`, `[MeSH Terms]`), so users can write MeSH searches.
- Mapping: PMID, DOI and PMCID; structured abstracts keep their labels ("BACKGROUND: …"); `MedlineDate` years ("2023 Nov-Dec") are read; collective authors stay whole; ORCID and the first affiliation are kept; `Retracted Publication` marks the record retracted; `Preprint`, `Congress` and `Technical Report` publication types map to TEz venue types, everything else to journal. Book records (`PubmedBookArticle`) are skipped and counted, as any unmappable item is.
- Identifiers: `pmid` and `pmcid` join `paper_identifier.scheme` (migration 0011). Deduplication matches on them like the other strong identifiers; PMIDs lose leading zeros and a `PMID:` prefix, PMCIDs always carry `PMC`. BibTeX imports read `pmid` and `pmcid` fields.
- PubMed joins the source chips (on by default, like the others) and `tez search --sources` (`pubmed`, alias `pm`).
- CLAUDE.md rule 1's network list now names PubMed (NCBI E-utilities).

## Consequences

- PubMed searches are slower than single-call sources (two calls per 200 records at 3 per second), well within a review's needs.
- With no key, a busy shared network can hit 429s; the HTTP client already backs off. A user API key (keyring, like OpenAlex and Semantic Scholar) can come later and would raise the rate to 10.
- MeSH terms of a record are not stored yet; they would help screening highlights and could come with the matrix work.
- Queries with more than 10,000 hits are capped by PubMed itself; the run's `total_reported` still shows the full count, so PRISMA reports what the database said.
