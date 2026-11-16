# 0023 — Highlight keywords belong to screening criteria

- **Status:** Accepted
- **Date:** 2026-11-16
- **Task:** 32 (title-abstract screening screen)

## Context

The screening screen (design 5.2) highlights terms in titles and abstracts: inclusion terms green, exclusion terms with a red underline, Turkish-safe. The plan's data model has nowhere to keep these terms. The design's legend ("inclusion term (I1, I2)") ties the terms to criteria.

The owner chose on 2026-11-16 to attach them to criteria rather than keep two lists per review.

## Decision

- `screening_criterion.keywords`: a JSON list of terms, empty by default (migration 0013). They are edited with the criterion in the review panel.
- The API keeps each term once, comparing them folded the way `tez.shared.text.fold` does ("Işık", "ışık" and "IŞIK" are one term); up to 50 terms of up to 100 characters.
- The screening screen matches terms on folded text (every i-like letter folds to "i", diacritics and case are ignored) and colours a match by its criterion's kind; hovering shows the criterion code. Archived criteria and those of the other stage are not highlighted.
- `GET /reviews/{id}/screening/{stage}/criteria` gives the stage's criteria with their keys and terms.

## Consequences

- Highlighting needs no extra table and follows a criterion's stage and archiving.
- The frontend has its own fold (`lib/text.ts`); it must stay in step with `shared/text.py`, and a shared test table checks both.
