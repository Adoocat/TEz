# 0035 — Literature matrix: derived rows, typed cells, conversions that keep what they cannot read

- **Status:** Accepted
- **Date:** 2026-11-26
- **Tasks:** 51 (matrix service), 52 (grid), 53 (cell evidence)

## Context

The plan has `matrix` and `matrix_column` (name, instruction, `data_type` text/number/enum/multi_enum/bool, options, order), `matrix_row` (paper, order) and `matrix_cell` (`value_text`, `value_json`, origin), with rows derived from the included papers. Acceptance: a type change loses no data without a word; the cells of an excluded paper are kept. TEz is used in every field, so numbers and yes/no may be written the Turkish or the English way.

## Decision

- **Rows are the papers whose current full-text decision is include**, reconciled where two reviewers decided, in the screening service's order (as quality assessment does). They are read, not stored as a list.
- **`matrix_row` is made when a paper's first cell is written, and it stays.** If the paper is excluded later, its row and cells stay. The API returns it after the included rows with `included: false`, and it cannot be edited until the paper is included again. The plan's `sort_order` on rows is left out: the order comes from screening, and sorting or grouping is the grid's view (Task 52).
- **A cell holds its value in the column's type in `value_json`**: a string, a number, true/false, an option id, or a list of option ids. Options have ids, so renaming an option changes no cell. Emptying a cell deletes it.
- **A type change writes every value out as text and reads it back as the new type.** A value that cannot be read without guessing is kept: `value_json` becomes null and `value_text` holds the text it was. The grid shows it marked; the next type or option change tries it again. Writing a value clears it. `dry_run` reports what would happen first (cells, converted, kept with their text).
- **Reading back does not guess.** Numbers: plain digits with one decimal point or comma. "1.420" and "12,345" are kept as text, since they mean different numbers in Turkish and English. Yes/no: yes/no, evet/hayır, var/yok, true/false, 1/0, x. Choices: option labels, Turkish letters folded; several are separated by ";" or a new line.
- **Yes/no becomes text in the user's words** (`true_text` and `false_text`, sent by the app in its language).
- **A column that becomes a choice column without options gets the choices written in its cells**, in the order first met.
- **Deleting a column or a matrix deletes its cells.** The user asks for it by name; the app asks before it (Task 52).

## Evidence (Task 53)

- **`cell_evidence` links a cell to anchors** (ADR 0033), several per cell. A passage can only back a cell in its own paper's row.
- **A passage keeps its cell:** clearing the value or a type change that empties it leaves the cell with its passages. Taking off the last passage of an empty cell removes the cell; the anchor itself stays.
- **Linking can fill an empty text cell with the passage** when asked (the reader's dialog asks by default). It never overwrites a value.
- **Coverage is derived** on every read: of the included papers' filled cells, how many rest on a passage, and how many rows rest wholly on passages. It is not stored (as PRISMA counts are not).

## Consequences

- Exclusions, re-inclusions and type changes can go back and forth without losing a cell.
- A kept cell is visible work for the user; it is never silently turned into a different number.
- `origin` is `manual` until Phase 5 writes `ai_accepted` for suggestions the user accepted (rule 2).
