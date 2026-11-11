# 0010 — BibTeX and RIS import: the same road as a search, and a report for what breaks

- **Status:** Accepted
- **Date:** 2026-11-11
- **Task:** 15 (BibTeX/RIS import)

## Context

IEEE Xplore, ACM DL, Scopus and Web of Science have no open API, but a jury may still expect them in a systematic search. Their exports (BibTeX, RIS) must enter the systematic record the way an API search does. Task 15: *the same `NormalizedRecord` → deduplication road, logged as a `search_run`. Acceptance: sample files, a report of bad input.* Exports are often damaged. Entries are cut short, keys repeat, titles are missing, and LaTeX is left in names.

## Decision

- **Parsers:** `bibtexparser` v2 and `rispy`, as the plan says, behind `modules/importers/{bibtex,ris}.py`. Each one returns a `ParsedFile`: the records it could read, plus one `EntryIssue` (code, line, key) for each entry it could not. A broken entry never stops an import.
- **BibTeX names are split before LaTeX is decoded,** and each part is then decoded with `pylatexenc`. A braced corporate author such as `{IEEE Team}` stays one name, and `{\c{C}}elik` becomes `Çelik`.
- **The RIS file is cut into records at each `TY  -` line here,** and each record is parsed on its own. `rispy` silently drops text it does not understand, which would hide a damaged export. A record with no `ER` line (a truncated download) is reported and skipped. Text outside any record is reported too.
- **Field problems are warnings, not errors.** A missing author, year or identifier, an unreadable year (`in press`) or an unusable link still imports the record. The preview counts these warnings and marks them in the sample table.
- **Encoding:** UTF-8 (with or without BOM), with a Windows-1252 fallback. The API takes the file as base64 in JSON (`content_base64`), so the server decides the encoding, not the browser. This needs no multipart dependency. The limit is 40 MB of base64.
- **Two steps.** `POST /imports/preview` writes nothing. It returns the format, counts (new, already found by a search, already in the library, repeated within the file), the issues, the warnings and the first five records. `POST /imports` stores the records. Preview matching uses the same `PaperIndex` as an import, with placeholder ids for records of the file itself.
- **Logging is the default, not a must.** With `log` (database name, search date, query), the import becomes a `search_run` with no `query_id`. Its `translated_query` holds the query the user ran at the database, `executed_at` holds the search date, and `total_reported` holds the number of entries in the file. The status is `partial` with `import.entries_skipped` when entries were skipped. The file is kept whole as the run's snapshot. The records can also go to the review's screening queue and/or the library.
- **One transaction per import.** An import is one file, so it is recorded whole or not at all.
- **`search_run.file_name`** *(addition to the plan's data model; migration 0005, plain `ALTER TABLE` like 0003)* names the file in the history. Search history shows "Imported: <file>". A search sent to sources has no file name.

## Consequences

- PRISMA counts for imported databases are derived exactly like API sources: retrieved from `search_result`, duplicates from the dedup matches.
- BibTeX citation keys are not stored. Citekey generation is a separate decision (Task 19 or export).
- Imported runs can be read by Task 23's `tez import` through the same `import_bytes` service, with `initiated_via=cli`.
- Collections as an import target come with Task 18.
- New dependencies: `bibtexparser` 2.1 (MIT), `rispy` 0.10 (MIT), `pylatexenc` 2.11 (MIT).
