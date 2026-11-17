# 0029 — Conflicts, reconciliation and Cohen's kappa

- **Status:** Accepted
- **Date:** 2026-11-17
- **Task:** 42 (conflicts and Cohen's kappa)

## Context

After Task 41, a review can hold the owner's decisions and a colleague's imported ones (ADR 0028). Task 42 asks for a "Conflicts" tab with both decisions side by side, reconciliation written as a new row, Cohen's kappa and percent agreement per stage, and PRISMA counted with reconciled decisions. Acceptance: kappa matches hand-worked examples; after reconciliation the conflict list is empty.

## Decision

- **What agrees.** Decisions are compared by what they do to a record (owner's choice, 2026-11-14). At title-abstract, include and maybe both send a record to full text, so they agree; only "advances" against "exclude" is a conflict. At full text, include, exclude, maybe and not retrieved are separate outcomes. Two exclusions agree even when their reasons differ.
- **Kappa and percent agreement** use the two reviewers' own decisions in force, over the records both decided at that stage, before any reconciliation. Kappa is (po − pe) / (1 − pe); it is undefined (shown as "—") with nothing to compare or when both used one category throughout.
- **Reconciling** writes the agreed decision through the screening service as a `consensus` row, with the usual rules (an exclusion needs a reason). The reviewers' own rows stay as they are. A conflict leaves the list once a `consensus` decision is in force for that record and stage; undoing it brings the conflict back.
- **A reconciled view, not a new owner.** The screening service gains a read-only view, `RECONCILED`: the owner's decisions with every `consensus` decision in their place. PRISMA counts, the included studies (formatted bibliography, quality assessment) and snowballing seeds read this view. With no `consensus` rows it equals the owner's decisions, so single-reviewer reviews are unchanged. The owner's screening queue keeps showing the owner's own decisions. A full-text reconciliation needs the reconciled title-abstract outcome to advance.
- **API:** `GET /reviews/{id}/decisions/agreement`, `GET /reviews/{id}/decisions/conflicts/{stage}` (with `reviewer` to pick a colleague when there are several; the first by name otherwise) and `POST …/conflicts/{stage}/reconcile`. `reconciled` joins `owner` and `consensus` as names a decision file cannot use.
- **UI:** "Conflicts" next to the stage tabs of screening (`/screening/conflicts`): agreement and kappa for both stages, the open conflicts with both decisions (reason and note), and buttons for the agreed decision.

## Consequences

- Reviews with more than two reviewers compare the owner with one colleague at a time.
- Kappa is reported per stage only; Fleiss' kappa or per-criterion agreement can come later.
- Rows of reviewers other than the owner and `consensus` never feed PRISMA directly; only a reconciliation does.
