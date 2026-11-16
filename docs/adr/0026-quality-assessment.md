# 0026 — Quality assessment: an optional, tool-neutral stage with only redistributable templates

- **Status:** Accepted
- **Date:** 2026-11-16
- **Task:** 38 (quality assessment)

## Context

The plan's data model lists `quality_question` (text, scale) and `quality_assessment` (paper_id, question_id, score, note) and leaves them out of Phase 1. ADR 0019 requires the stage to stay tool-neutral: users bring their own questions and scale, or start from a common checklist (Kitchenham, JBI, risk-of-bias tools such as RoB 2), and some fields use none at all. Task 38 makes it an optional stage for the studies included at full text, hidden on the review panel while it is off.

Two things the plan does not settle: where the on/off switch lives, and which checklists TEz may bundle. TEz is MIT-licensed and bundled data must be redistributable. We checked each candidate (November 2026):

| Tool | Terms found | Bundled? |
| --- | --- | --- |
| Kitchenham & Charters (2007), EBSE-2007-01 quality checklist | "© Kitchenham, 2007"; no licence | No: unclear |
| JBI Critical Appraisal Tools | "© JBI. All rights reserved"; use granted for research only, other uses need written permission | No |
| RoB 2 (Cochrane) | CC BY-NC-ND 4.0 | No: non-commercial, no derivatives |
| CASP checklists | CC BY-NC-SA | No: non-commercial |
| NHLBI Study Quality Assessment Tools (six tools, last updated July 2021) | U.S. Government work (17 U.S.C. § 105); no copyright notice on the page; NHLBI says its site's content is public domain unless noted | Yes |

## Decision

- **Schema (migration 0017).** Three tables in a new `modules/quality`:
  - `quality_setting`: one row per review with `enabled`. No row means off. This is a third table the plan did not list; the owner chose it over a `review.quality_enabled` column so the quality module stays self-contained and the reviews module is untouched.
  - `quality_question`: `review_id`, `text`, `guidance`, `scale_json`, `sort_order`, `template` (the bundled template it came from, for the methods section). Each question carries its own scale, so a set can mix "Yes / No / Not applicable" items with a closing "Good / Fair / Poor" rating.
  - `quality_assessment`: `review_id`, `paper_id`, `question_id`, `answer`, `note`, `reviewer` (default `owner`, as on `screening_decision`); unique per review, paper, question and reviewer. The plan's `score` is named `answer` and holds the chosen option's stable `value`; the numeric score is read from the scale, so relabelling or rescoring a scale never rewrites answers.
- **Answers are current state, not history.** Rule 3's append-only tables are the search and screening ones; an answer is edited in place, and clearing both answer and note removes the row.
- **Derived, never stored.** Progress and totals are computed on each read: the total sums the chosen options' scores, out of the best reachable score for the questions that count. A question counts when its scale has scores and it is unanswered or answered with a scored option, so "Not applicable" takes it out of the maximum.
- **Guards.** A scale change may relabel, rescore or add options but not drop a value some answer uses (`quality.scale_value_in_use`); an answered question cannot be deleted (`quality.question_in_use`); only papers included at full text can be assessed (`quality.paper_not_included`). "Included at full text" comes from the screening service (`ScreeningService.included`, Task 31), never from the decisions table.
- **Templates.** Only the six NHLBI tools are bundled, with their questions verbatim and their source, version and licence shown in the UI. Kitchenham, JBI, RoB 2 and CASP are left out. Users can paste the items of any checklist they are licensed to use, one per line; the text stays in their library. Generic scale presets (Yes / Partly / No, Yes / No / Unclear / Not applicable, Low risk / Some concerns / High risk, Good / Fair / Poor) are TEz's own.
- **Languages.** Template questions keep the tool's own wording (English). Scale labels exist in every UI language and the chosen language is copied into the review when a template or preset is used; after that they are the review's own text.
- **The review panel** shows a quality stage card only while the stage is on, and a switch to turn it on or off. Off hides the stage and keeps every question and answer.

## Consequences

- Health and other fields get ready tools; reviews that follow Kitchenham, JBI, RoB 2 or CASP type the items in or paste them. If one of those publishers grants redistribution later, adding it is a data change in `modules/quality/templates.py`.
- `docs/licenses.md` lists the NHLBI tools as bundled data.
- One question set per review. Reviews that apply different tools to different study designs (for example, an RCT tool and a cohort tool) need several sets; that, a quality column in exports, and a second assessor's answers with agreement are noted for later.
