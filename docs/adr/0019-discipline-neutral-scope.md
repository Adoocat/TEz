# 0019 — A tool for every discipline: two roads for sources, PRISMA 2020 first, formatted bibliographies

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** none (scope decision between Phase 1 and Phase 2)

## Context

The plan's defaults came from the owner's own thesis: a software engineering review. The method default is Kitchenham SLR with snowballing. The sources lean to computer science (arXiv, DBLP). The risk table says the jury may expect IEEE Xplore, ACM DL and Scopus. The sample matrix columns are about code models.

After Phase 1, a Turkish academic (a psychologist) reviewed the app. In their field, systematic reviews are kept in Excel by hand, and they saw TEz as a fit. They asked for three things:

1. Turkish databases: TR Dizin for articles, and YÖK Ulusal Tez Merkezi for theses ("has this been done as a thesis already?").
2. Formatted bibliographies in the style a field uses (APA in psychology, other styles in health), as Mendeley does.
3. Coverage of the databases researchers actually use.

The owner then set the scope: TEz is for research and theses in **every** discipline. That includes the humanities, law, education, health and engineering, with no field group singled out. Users will expect Google Scholar, JSTOR and similar databases.

What we checked (November 2026):

- **Google Scholar** has no API. Its terms forbid automated queries, and it answers them with CAPTCHAs. Zotero, Covidence and Rayyan do not search it either.
- **JSTOR**: we found no public search API. Search results can be exported as RIS, up to 400 at a time.
- **Scopus, Web of Science, ScienceDirect, EBSCO, ProQuest, PsycINFO, HeinOnline**: paid, with institutional or no API access. All of them export RIS, BibTeX or their own text formats.
- **TR Dizin** says publication data is available through an API service, and a JSON search endpoint is described by third parties. We have not found official terms of use. Its web interface exports BibTeX.
- **YÖK Ulusal Tez Merkezi** has no official API. The community clients scrape the site. Some full texts are closed or need an e-Devlet login.
- **PubMed** (E-utilities) and **Europe PMC** have free, documented APIs. So do DOAJ, ERIC and CORE, and DergiPark has OAI-PMH.
- **OpenAlex**, already a source, covers all fields, including books and book chapters. It is the closest legal match to Google Scholar's breadth.
- **Citation styles:** the Citation Style Language (CSL) has thousands of styles (APA 7, MLA, Chicago, Vancouver, IEEE…) and a Turkish locale. The styles are CC BY-SA 3.0 (data, attribution needed). `citeproc-js` is AGPL/CPAL, so rule 6 rules it out. `citeproc-py` is the Python processor, but its license is not yet confirmed.

## Decision

- **Scope.** TEz serves systematic reviews and theses in every discipline. Defaults, sample data and wording must not assume a field. The owner's thesis topic only feeds the demo library.
- **Two roads for sources.**
  - *API road:* a database with an open, documented API whose terms allow this use becomes a provider behind the `Protocol` adapter (ADR 0008).
  - *File road:* every other database comes in through its export (Task 15, ADR 0010). Imports are already logged as a `search_run` with the database name, the search date and the query, and PRISMA counts them like an API source.
  - **The file road is first-class, not a fallback.** It gets database presets and export guides (below).
- **No scraping.** TEz does not scrape a site whose terms forbid automation or that blocks bots (Google Scholar, JSTOR). It does not bypass CAPTCHAs. A source with unclear terms is not added until the terms are clear.
- **New providers, one at a time.** Each new API source needs the owner's approval, a check of the current API documents, an ADR, and an update of the network list in CLAUDE.md rule 1. Candidates, in no fixed order: PubMed, Europe PMC, DOAJ, ERIC, CORE, DergiPark (OAI-PMH), TR Dizin. The order is set when Phase 2 is planned.
- **Method default: PRISMA 2020.** New reviews default to PRISMA 2020. Kitchenham SLR (and later systematic mapping) remains a choice. Snowballing stays a method for every field. Today's review form still defaults to `kitchenham_slr`; that changes with Phase 2.
- **Grey literature in PRISMA.** The PRISMA diagram is designed in Phase 2 with the "other methods" branch, covering theses, reports and registers as well as snowballing. A thesis source added later then needs no PRISMA change.
- **Formatted bibliographies with CSL**, rendered in the backend (never `citeproc-js` in the frontend). At least APA 7, MLA, Chicago, Vancouver and IEEE, in Turkish and English. Institute thesis styles can come later as custom CSL files. This lands at the end of Phase 2, because its main scope ("the studies included in this review") needs screening decisions.
- **Theses (YÖK Tez) come in Phase 4,** with saved-query alerts, because the need ("which theses are being written now") is monitoring. It starts as an experimental source, off by default, and only if its terms allow it.
- **Out of scope:** a Word cite-while-you-write plugin. Zotero export (Phase 6) covers that road.

## Consequences

- The plan's decision table, risk table and "missing from the plan" list are updated. A new plan section places each item in a phase.
- Phase 2 planning starts with: the method default, database import presets and export guides, the grey-literature branch of PRISMA, and the order of new providers.
- Quality assessment (`quality_question`, `quality_assessment`) must stay tool-neutral. Users bring their own questions and scales or start from a common checklist (Kitchenham, JBI, risk-of-bias tools such as RoB 2). Some fields use none at all. The schema already allows this; no Kitchenham-only checklist is hard-coded.
- Publication-type filters and exports must handle books, book chapters and theses as well as journals and conferences. The BibTeX writer currently writes every thesis as `@phdthesis`; master's theses need `@mastersthesis` (noted in progress, "Later").
- Open questions moved to `docs/progress.md`: two-reviewer screening with Cohen's kappa in Phase 2 or later; the terms of use of TR Dizin and YÖK Tez; the license of `citeproc-py`.
- No code changes with this ADR.
