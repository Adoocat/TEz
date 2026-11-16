# 0024 — Snowballing is recorded as search runs

- **Status:** Accepted
- **Date:** 2026-11-16
- **Task:** 36 (snowballing)

## Context

Task 36 follows included papers' references (backward) and citing papers (forward) through OpenAlex and Semantic Scholar, in numbered rounds (Wohlin 2014). PRISMA 2020 counts these records in its "other methods" branch, per round, and every PRISMA count must be derived from append-only records (CLAUDE.md rules 3 and 4). The plan names `review_record.origin` (`citation_backward` / `citation_forward`) and `origin_ref`, but not where a round's answers and their numbers live.

## Decision

- Each source's answer for one seed and one direction is a `search_run`, like a database search: `method` (`database`, `citation_backward`, `citation_forward`), `snowball_round` and `seed_paper_id` are new columns (migration 0014). Its papers are `search_result` rows, matched against the library exactly like search results, so duplicates merge the same way.
- One snowballing action (seeds × directions × sources) shares a `search_id` and runs as one worker job (`snowball.round`). A retried job skips the answers already on record and only takes in what is missing.
- Papers not yet in the review become `review_record`s with the citation origin and the seed in `origin_ref`; a paper already there keeps its first origin. New records enter title-abstract screening.
- Rounds: a paper from a database search or added by hand is round 0; one found by round n is round n; an action's round is one more than its latest seed's. Seeds must be included in screening (title-abstract or full text).
- The search history lists only database searches; snowballing has its own list on the review panel.

## Consequences

- PRISMA (Task 34) reads snowballing per round from `search_run` and `review_record`; nothing is stored as a count.
- The migration rebuilds `search_run` (a named foreign key needs batch mode on SQLite) and recreates its append-only triggers.
- Network access stays within the two sources already allowed (CLAUDE.md rule 1).
